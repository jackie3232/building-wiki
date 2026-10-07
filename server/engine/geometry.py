"""
④ 几何计算引擎 + ⑤ 几何造型引擎(BOX 出口)
------------------------------------------------
输入 ：**自包含实例图谱**。生产路径 = Agent 侧装配后上传云存储，经 MCP
       generate_building 以 cos:<objectKey> 引用传入（见 storage.read_instance）；
       本地调试可直接传 dict。
       自包含：data 块为实例数据（拓扑+尺度具体值），appliedRules 为规则快照。
       ④ 只读 instance 整体（data + appliedRules），不碰外部 dict.json / rules.json。
       ① 归 Agent 侧（LLM 出骨架 → skill 的 assemble 装配）；本容器不设 ①，④ 不读外部知识文件。
输出 ：⑤ 体素 BOX 清单（场景坐标：Y-up，单位米）
       每个 box = {x,y,z, w,h,d, role, label, color}

分层（见 几何计算引擎IO契约.md）：
- compute_geometry(instance) = ④：instance -> 构件列表（连续几何，绝对坐标，无 color/label）
- geometry_to_boxes(geo)     = ⑤：构件 -> box 像素网格（选 Box 基元 + 补 label/color）
- instance_to_boxes(inst)    = 串联 ④->⑤（便捷入口，供本地验证）
- build_tour_path(inst, geo) = ④ 布局 + 实际构件 -> 游览路线 DATA（纯展示层派生，实时生成，不回灌 ④/⑤）

设计铁律（见 架构设计总览.md §7/§9/§14、几何计算引擎IO契约.md）：
- 零坐标：instance 不含 x/y/z；④ 据「间」模数与拓扑算绝对坐标（④ 本职）。
- ④ 只吃 instance（data + appliedRules），模数/尺度等换算标准全部从图谱取，无一硬编码。
- 输出是「构件」不是「box」也不是「空间」；构件 : box = 图像 : 像素（box 由 ⑤ 多体素化）。
- ⑤ 只做造型策略（MVP = 无 B-rep 的 BOX 体素），未来可切 Box/Brep 等基元，不污染 ④。
"""
import math

# 知识包唯一权威源 = 智能端 Skill 目录（functions/.../traditional-building/packs）。
# 服务端运行时(④⑤/标签)绝不读盘包，只引用实例图谱自带的 appliedRules/appliedDict 快照。

# —— ④ 不在此文件固定任何规制数字 ——
# 模数 / 房屋高度(等级) / 墙厚 / 门洞 / 门体面阔 / 附属构件尺寸，全部来自
# instance.appliedRules（规则库快照），缺失即报错（见 _norms_get），
# 迫使在知识中心修正，而不是在代码里兜底。

# —— 游览路线派生的落位参数（build_tour_path 用，纯展示层语义，不进图谱）——
TOUR_OUTSIDE = 3.5            # 起点：最南院门外沿门轴再外扩的距离（米）
TOUR_STEP = 0.30              # 台基面高度：穿门/穿堂时的落脚面（米）
TOUR_PAUSE = 1.6              # 庭心驻足时长（秒）
TOUR_END_PAUSE = 2.4          # 终点回望时长（秒）
TOUR_DOOR_DEPTH_HALF = 0.6    # 穿门点距门体中心的纵向偏移，使落点落在门道内而非墙面（米）
TOUR_CORNER_R = 0.80          # 拐点过渡半径：宅门在东南角，把直角的两次 90° 硬折拆成 45°+45°（米）
TOUR_LOOK_DEG = 35            # 驻足"轻扫一眼"的偏转角（度，负=偏西）；替代原先甩头 90°/掉头 180°

# 体素边长（米）。越小越细、box 越多；越大越省、体素感越弱。MVP 提速版适中取值。
# 体素边长（米）。越小越细、box 越多；越大越省、体素感越弱。
# 0.3 的取值依据：须容下古建最小可读构件——台阶单级(≈0.2~0.3)、墙厚(0.3)、
# 台明一阶(0.3)；0.6 时这些全是"半格"，体素化后墙消失/台基被抹平/台阶看不出级数。
# 本值属【造型层 ⑤】的实现参数，不写入知识包、④ 不感知（换 B-rep 只改 ⑤）。
VOXEL_SIZE = 0.3

# 中文名一律取自命名字典 —— 但 ⑤ 造型层与巡游路径都不再内置词表、也**绝不回读盘上 dict.json**。
# 自动化端(④⑤)只引用实例图谱自带的 appliedDict 快照（智能端装配时已按需裁剪好的命名子集），
# 这正是「自动化端不碰知识中心、只引用实例图谱」的分界原则。
# 历史教训：早年内置表与字典漂移（houmen 字典有「后门」、内置表没有 → 屏幕显示 "houmen"），
# 故中文名必须且只从实例图谱快照取。
def _labels_from_applied(applied):
    """实例 appliedDict(命名字典按需子集) -> 扁平 {key: 中文名}（跨类目合并）。

    这是 ⑤ 中文名的唯一来源：自动化端不读知识包，只引用实例图谱自带快照。
    applied 结构同 dict.json（按类目分组的 {key: {label, ...}}），仅保留用到的词条。
    """
    flat = {}
    if not isinstance(applied, dict):
        return flat
    for cat, items in applied.items():
        if cat == "meta" or not isinstance(items, dict):
            continue
        for k, v in items.items():
            if isinstance(v, dict) and isinstance(v.get("label"), str):
                flat[k] = v["label"]
    return flat


def _label_of(key, dflt=None, table=None):
    """key -> 中文名（字典为准）。字典缺词条：给了 dflt 就回落，没给则报图谱缺陷
    —— 不静默把拼音 key 当成中文名吐出去（那正是漂移发生时的表现）。

    自动化端不回读盘包：table 须由调用方从 instance.appliedDict 传入（见
    _labels_from_applied），本函数不再隐式读盘。"""
    hit = (table or {}).get(key)
    if hit:
        return hit
    if dflt is not None:
        return dflt
    raise ValueError(
        "图谱缺陷：dict.json 缺词条 %r —— 中文名一律取自命名字典，"
        "新增 role/key 须先在 dict.json 补词条" % (key,))


def _entry_of(applied, key):
    """在 appliedDict（命名字典快照，按类目分组）里跨类目查一个词条；查不到返回 {}。"""
    if not isinstance(applied, dict):
        return {}
    for cat, items in applied.items():
        if cat == "meta" or not isinstance(items, dict):
            continue
        e = items.get(key)
        if isinstance(e, dict):
            return e
    return {}


def _form_of(applied, key):
    """词条的形体声明（`dict.<类目>.<key>.form`）—— ④ 的造型依据。

    **这是「引擎零风格硬编」（架构总纲 §7 判据 1）的落点。**
    门的落位（east-end / west-end / center）、是否带门楼、房/墙/廊/壁的形体原型，
    一律由知识包声明；④ 只按声明执行，代码里不出现任何具体建筑角色名。
    历史包袱：这些事实原先是 geometry.py 里的 if/elif 分支（`gate == "zhaimen"` 等）。
    """
    f = _entry_of(applied, key).get("form")
    return f if isinstance(f, dict) else {}


def _hex_to_int(s, ctx):
    """'#C0504D' -> 0xC0504D。缺 / 非法即报图谱缺陷（图示色属知识事实，代码不兜底）。"""
    if not isinstance(s, str):
        raise ValueError("图谱缺陷：%s 缺 color（须为 '#RRGGBB'）—— 新增 role 须先在 "
                         "dict.json 补 form/color" % ctx)
    t = s.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError("图谱缺陷：%s 的 color %r 不是 '#RRGGBB'" % (ctx, s))
    return int(t, 16)


def _colors_from_applied(applied):
    """命名字典快照 -> 扁平 {key: 颜色int}（跨类目合并）。⑤ 上色的唯一来源。"""
    flat = {}
    if not isinstance(applied, dict):
        return flat
    for cat, items in applied.items():
        if cat == "meta" or not isinstance(items, dict):
            continue
        for k, v in items.items():
            if isinstance(v, dict) and isinstance(v.get("color"), str):
                flat[k] = _hex_to_int(v["color"], "dict 词条 %r" % (k,))
    return flat

def _norms_get(norms, path, ctx=""):
    """按路径从 appliedRules.norms 取值；缺失即报错。

    ④ 只消费实例图谱，不为规制数字在代码里兜底——缺字段是图谱缺陷，必须回知识中心修，
    否则错误会被静默掩盖成「看起来能跑」。
    """
    cur = norms
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            raise ValueError(f"图谱缺陷：appliedRules.norms.{'.'.join(path)} 缺失（{ctx}）")
        cur = cur[k]
    return cur


def _spec_get(spec, norms, role, key):
    """建筑自身属性优先，回落 norms.<role>.<key>（「这一座」覆盖「这一类」）。"""
    if isinstance(spec, dict) and spec.get(key) is not None:
        return spec[key]
    return (norms.get(role) or {}).get(key)


def _role_height(norms, role, spec=None, ctx=""):
    """角色高度：优先建筑自带 height，回落 norms.<role>.height，再回落 heightDefault。"""
    h = _spec_get(spec, norms, role, "height")
    if h is None:
        h = _norms_get(norms, ("room", "heightDefault"), f"{role}.height 未声明，取回落基准")
    return float(h)


def _dim(role_obj, key, default):
    return (role_obj or {}).get(key, default)


def _role_of(obj, default):
    if isinstance(obj, dict):
        return obj.get("role", default)
    return default


def _gate_role(node, ctx):
    """门体 role：节点不存在返回 None；节点在、role 缺 → 报图谱缺陷。

    门的种类事实源是知识包（enclosure.*.gate.role / beimen.role），④ 只回读、不写死常量；
    缺 role 时静默回落，会让「墙上有门却不开口」这类错误永远看不出来。
    """
    if not node:
        return None
    r = node.get("role") if isinstance(node, dict) else None
    if not r:
        raise ValueError(
            f"图谱缺陷：{ctx} 声明了门体却缺 role —— 门的种类须由知识包声明")
    return r


def _layout(instance):
    """④ 布局定位：算每院占地(w/d)与南北中心(zc)。

    compute_geometry 与 build_tour_path 共用同一份布局计算，杜绝公式两处实现产生漂移。
    返回 (plotted, norms, modus)；plotted[i] 含 {w,d,nd,sd,zc,bei,nan,dong,xi,c}。
    """
    data = instance.get("data", instance)
    applied = instance.get("appliedRules", {})
    norms = applied.get("norms", {}) or {}
    modus = float(_norms_get(norms, ("modus",), "模数"))

    courtyards = sorted(data.get("courtyards", []), key=lambda c: c.get("sequence", 0))
    if not courtyards:
        return [], norms, modus

    # 每院占地：w 沿 X（面阔），d 沿 Z（进深）。
    # 两趟：院深依赖【参照院面阔】(norms.courtDepthOf.refRole)，故先齐备各院面宽再定院深。
    # 本层只按图谱已给的 role 取参照院，不重算院角色、不内嵌角色名。
    def _span(c):
        """本院面宽（沿 X）：取北/南任一有 miankuo 的建筑 × 模数；两面皆无则报图谱缺陷。"""
        enc = c.get("enclosure", {})
        ref = enc.get("bei") or enc.get("nan")
        if not isinstance(ref, dict) or not isinstance(ref.get("miankuo"), (int, float)):
            raise ValueError(
                "图谱缺陷：第 %s 进 南北两侧均无带 miankuo 的建筑，算不出院落面阔"
                % c.get("sequence"))
        return ref["miankuo"] * modus

    spans = [(c, _span(c)) for c in courtyards]
    cdo = _norms_get(norms, ("courtDepthOf",), "院落进深(参照院面阔倍数)")
    if not isinstance(cdo, dict):
        raise ValueError(
            "图谱缺陷：appliedRules.norms.courtDepthOf 须为对象"
            "（含 refRole / byRole / default），实际 %r" % (type(cdo).__name__,))
    ref_role = cdo.get("refRole")
    by_role = cdo.get("byRole") or {}
    # 参照院面宽：role==refRole 的那一院；单进院/自指时以自身为基准。
    ref_w = next((w for c, w in spans if c.get("role") == ref_role), None)

    plotted = []
    for c, w in spans:
        enc = c.get("enclosure", {})
        bei, nan, dong, xi = enc.get("bei"), enc.get("nan"), enc.get("dong"), enc.get("xi")
        nd = _dim(bei, "jinshen", 0) * modus   # 缺房则进深记 0（无幽灵进深）
        sd = _dim(nan, "jinshen", 0) * modus
        base_w = ref_w if ref_w is not None else w
        role = c.get("role")
        ratio = by_role.get(role, cdo.get("default"))
        if not isinstance(ratio, (int, float)):
            raise ValueError(
                "图谱缺陷：appliedRules.norms.courtDepthOf 未给 role=%r 的倍数，"
                "且无 default" % (role,))
        court_depth = base_w * ratio        # 进深 = 参照院面宽 × 本倍数（乘算仅此一处）
        d = nd + court_depth + sd
        plotted.append({"w": w, "d": d, "nd": nd, "sd": sd, "bei": bei, "nan": nan,
                        "dong": dong, "xi": xi, "c": c})

    total = sum(p["d"] for p in plotted)           # 院落间紧贴：双墙相邻无间隙(gap=0)
    z = -total / 2                                 # 序列1=最南(-Z)，序列N=最北(+Z)
    for p in plotted:
        p["zc"] = z + p["d"] / 2
        z += p["d"]
    return plotted, norms, modus


def _graph_data(instance, fn):
    """形状闸：取出实例图谱的 data 块，并确认它确实带 courtyards；缺则报图谱缺陷。

    为什么必须有这道闸（本地实测复现）：courtyards 缺失/为空时 compute_geometry 原本
    **静默返回 []**，调用方（LLM）会把它读成「成功但空」，于是换个写法继续试——
    实测盲试十余分钟才放弃。缺字段一律报错是本项目既有约定（见 _norms_get 注释），
    这里补上同一约定，让错误在出口暴露。

    另：形状闸必须排在 _layout **之前**。原先 {} 会先撞上「appliedRules.norms.modus
    缺失」，而该报错会把模型引向**编一个模数数字**（实测它随即加了 modus:0.1），
    反而绕开了真正的病根——「你喂进来的是骨架，不是装配后的图谱」。先判 courtyards
    才指得准方向。
    """
    if not isinstance(instance, dict):
        raise ValueError("图谱缺陷：%s 的 instance 须为对象（实例图谱），收到 %s"
                         % (fn, type(instance).__name__))
    data = instance.get("data", instance)
    if not isinstance(data, dict):
        raise ValueError("图谱缺陷：%s 的 instance.data 须为对象，收到 %s"
                         % (fn, type(data).__name__))
    courtyards = data.get("courtyards")
    if not isinstance(courtyards, list) or not courtyards:
        raise ValueError(
            "图谱缺陷：%s 的 data.courtyards 缺失或为空 —— 入参须是**装配后的自包含实例"
            "图谱**（meta/data/appliedRules，建筑声明带数值），不是只写了 role 的骨架；"
            "骨架请先经装配器（skill 的 assemble.mjs）补全数值再调用" % fn)
    return data


def compute_geometry(instance):
    """④ 几何计算：instance -> 构件列表。每个构件 = {role, center:{x,y,z}, size:{w,h,d}}。

    - 只读 instance（data + appliedRules），不硬编码任何规制数字。
    - 输出是构件（连续几何），不是 box、不是空间。庭院虚空不输出。
    - 算不出任何构件即报图谱缺陷 —— **绝不静默返回 []**（见 _graph_data 的 why）。
    """
    _graph_data(instance, "compute_geometry")
    plotted, norms, modus = _layout(instance)
    t = float(_norms_get(norms, ("room", "thickness"), "墙面线偏移基准（取房间墙厚）"))
    applied = instance.get("appliedDict") or {}
    # 墙种值域与分组（appliedRules.wall）：④ 按 ring.<side>.kind 取墙高厚（2026-09-28 接上消费者）。
    # 只有「基底院墙」那一组（appliesTo=ringBase）决定院墙高厚；建筑用墙（houyanqiang）回落 norms.wall。
    _wall = (instance.get("appliedRules") or {}).get("wall") or {}
    wall_kinds = _wall.get("kinds") or {}
    wall_role = _wall.get("ref")
    if not isinstance(wall_role, str) or not wall_role:
        raise ValueError("图谱缺陷：appliedRules.wall.ref 缺失 —— 独立院墙的角色 key 须由知识包声明")
    ring_kinds = set()
    for grp in (_wall.get("taxonomy") or {}).values():
        if isinstance(grp, dict) and grp.get("appliesTo") == "ringBase":
            ring_kinds.update(grp.get("kinds") or [])
    if not ring_kinds:
        raise ValueError("图谱缺陷：appliedRules.wall.taxonomy 无 appliesTo=ringBase 的墙种分组")
    geometry = []
    for idx, p in enumerate(plotted):
        zc = p["zc"]
        w, d = p["w"], p["d"]
        nd, sd = p["nd"], p["sd"]

        # 南北向房屋：长边沿 X（面阔）、厚沿 Z（进深）。开口朝向由「房屋在院的哪一侧」决定
        # （北侧房朝南、南侧房朝北）——这是几何事实，不靠角色名的字面量硬判。
        for side in ("bei", "nan"):
            node = p[side]
            if not node:
                continue
            depth = nd if side == "bei" else sd
            if depth <= 0:
                continue
            z_side = zc + d / 2 - nd / 2 if side == "bei" else zc - d / 2 + sd / 2
            # 中轴 x 传**整型 0**（不是 0.0）：构件坐标经 round() 后要逐字节与改动前一致，
            # 0 与 0.0 在 JSON 里是两个不同的字面量，会污染零漂移核验。
            geometry.extend(_geo_house(node, 0, w, depth, z_side,
                                       "S" if side == "bei" else "N", norms, applied))
        # 东西向房屋：长边沿 Z（面阔），厚沿 X（进深）。
        # Z 向填充「北房檐 -> 南房檐」空隙，中心 = zc + (sd-nd)/2，
        # 使其与北房只在角上相接、体积不重叠（修此前 厢房/北房 空间重叠）。
        ew_z = zc + (sd - nd) / 2
        for side in ("dong", "xi"):
            node = p[side]
            if not node:
                continue
            ed = _dim(node, "jinshen", 0) * modus
            if ed <= 0:
                continue
            el = _wing_length(node, norms, d, nd, sd, modus)
            cx_side = (w / 2 - ed / 2) if side == "dong" else -(w / 2 - ed / 2)
            geometry.extend(_geo_house(node, cx_side, ed, el, ew_z,
                                       "W" if side == "dong" else "E", norms, applied))

        # 院墙上的门本体（不挂在任何建筑上）：门道南北贯通，落在本院北/南界。
        enc = p["c"].get("enclosure", {})
        # 院墙门(beimen/nanmen)门屋落点随院墙中心同步内移 t/2，确保门屋与墙洞同轴
        # （院墙中心已从院边界 zN 内移至建筑后檐墙中心 zN - t/2，见 _geo_wall_ring）。
        for slot, z_edge in (("beimen", zc + d / 2 - t / 2), ("nanmen", zc - d / 2 + t / 2)):
            if enc.get(slot):
                grole = _gate_role(enc[slot], "enclosure.%s" % slot)
                geometry.extend(_geo_gate_standalone(grole, z_edge, norms, _form_of(applied, grole)))

        # 围合构件（实体）：按词条声明的形体原型分派，代码不认角色名。
        for per in (p["c"].get("peripheral") or []):
            if not isinstance(per, dict):
                continue
            prole = per.get("role")
            kind = _form_of(applied, prole).get("kind")
            if kind == "colonnade":
                geometry.extend(_geo_colonnade(prole, w, nd, zc, d, norms))
            elif kind == "screen-wall":
                geometry.append(_geo_screen_wall(prole, w, sd, zc, d, norms))
            elif kind == "void":
                pass                       # 声明为虚空者不产构件（如庭院）
            else:
                raise ValueError(
                    "图谱缺陷：附属构件 %r 的形体原型 %r ④ 不认识（dict.%s.form.kind 缺失或非法）"
                    % (prole, kind, prole))

        # 院墙环（boundarySegmentRealization）：先画完整一圈墙、门(gate)开缺；
        # 贴边建筑（后檐墙/山墙）的实现不在此预判——统一交给末尾 _resolve_boundary 去重。
        if p["c"].get("perimeter"):
            geometry.extend(_geo_wall_ring(p["c"], w, zc, d, norms, applied,
                                           draw_south=(idx == 0), wall_kinds=wall_kinds,
                                           ring_kinds=ring_kinds, wall_role=wall_role))

    # 边界去重：同一条墙线上建筑墙优先于独立院墙，被覆盖的院墙段按区间相减掉。
    resolved = _resolve_boundary(geometry, norms, wall_role)
    # 兜底闸：形状闸只认得住「有没有 courtyards」，认不住「courtyards 里全是空壳」。
    # 算不出构件一律报错，保持「绝不静默返回 []」这条不变式对整个函数成立。
    if not resolved:
        raise ValueError(
            "图谱缺陷：compute_geometry 算不出任何构件 —— 各院 enclosure 为空且无院墙，"
            "或构件全部被边界去重消掉；图谱结构不完整")
    return resolved


def _glance(px, pz, heading, deg, dist):
    """驻足"轻扫一眼"的看点：自行进方向偏转 deg 度、取 dist 距离处的点（负=偏西，正=偏东）。

    它是**展示层**的落位，不进图谱、不回灌 ④/⑤。原先的 look 直接指向构件中心（西厢/来路），
    等于每次驻足甩头 90°、末点掉头 180°；偏转后镜头只小幅侧移。
    """
    a = heading + math.radians(deg)
    return [round(px + math.sin(a) * dist, 3), round(pz + math.cos(a) * dist, 3)]


def build_tour_path(instance, comps=None):
    """④ 布局 + 实际构件坐标 -> 游览路线 DATA（实时派生，不落盘、不进图谱、不回灌 ④/⑤）。

    语义骨架取自实例图谱（每院南/北界是谁、有无门、北房是不是穿堂），坐标取自 ④ 几何
    （_layout 的院深/院心 + 实际构件里的宅门门道中心）。故进数 1/2/3/4 自适应——
    不存在「按三进写死」导致的越界、穿不存在的门、走进不存在的房子。

    统一模板（逐院）：进院门 -> 庭心驻足 -> 出下道门；首院北门后补「折向中轴」（宅门在
    东南角、不在中轴），末院北面无门，止于北房之前、回望来路收尾。

    返回 [{x, y, z, label, pause?, look?}]，与 ⑤ 体素 BOX 同源坐标（米，Y-up）。
    """
    plotted, _norms, _modus = _layout(instance)
    if not plotted:
        return []

    # 巡游中文名同样只引用实例图谱快照（自动化端不回读盘包）。
    _tour_labels = _labels_from_applied(instance.get("appliedDict"))

    # 对外宅门在角上、不在中轴：门道中心 x 直接取实际构件里**该门角色**的中心
    # （避免公式两处实现漂移）。门角色取自图谱声明，代码不硬编任何门名。
    _enc0 = (plotted[0]["c"].get("enclosure") or {}) if plotted else {}
    _outer_gate = (((_enc0.get("nan") or {}).get("gate")) or {}).get("role")
    gxs = [g.get("center", {}).get("x", 0.0)
           for g in (comps or []) if _outer_gate and g.get("role") == _outer_gate]
    gate_x = round((min(gxs) + max(gxs)) / 2.0, 3) if gxs else 0.0

    path = []
    last = len(plotted) - 1
    for i, p in enumerate(plotted):
        zc, d, nd, sd = p["zc"], p["d"], p["nd"], p["sd"]
        enc = p["c"].get("enclosure", {}) or {}
        name = p["c"].get("name") or f"第{i + 1}进"
        z_north = zc + d / 2
        z_south = zc - d / 2
        z_court = zc + (sd - nd) / 2.0        # 露天庭院中心（与 ④ 厢房的 ew_z 同源）

        # —— 进院：仅首院有对外宅门（东南角）。其余院是「经上一院北界」进入的，
        #      其路径点已落在上一院的「出下道门」段（垂花门 / 穿堂北口），此处不重复 ——
        if i == 0:
            if (enc.get("nan") or {}).get("gate"):
                gz = z_south + sd / 2.0                    # 宅门门道轴线（嵌在倒座房进深内）
                path.append({"x": gate_x, "z": round(z_south - TOUR_OUTSIDE, 3),
                             "y": 0.0, "label": "宅门外"})
                path.append({"x": gate_x, "z": round(gz, 3), "y": TOUR_STEP, "label": "穿过大门"})
                # 出倒座后檐入庭院，走「影壁南面 ↔ 倒座北檐」这条东西向走道的中心：
                #   倒座北檐 = 南界+sd；影壁南面 = 南界+sd+zOffset-厚/2（zOffset=2.0 → +1.75）。
                #   走道 [+0.5, +1.75]，取中心 +1.0 —— 人体半宽 0.25 在 0.5m 占据格下两侧均有余量。
                #   （旧值 +0.6 是 zOffset=1.2 时走道仅 0.95m 的窄缝，实测巡游擦碰倒座/影壁。）
                z_in = z_south + sd + 1.0
                r = min(TOUR_CORNER_R, z_court - z_in - 0.45)   # 过渡半径受院深受限（外院很浅时会收小）
                if abs(gate_x) > 0.01 and r >= 0.25:       # 宅门偏东南，需横向折回中轴
                    # 只切「中轴」那个拐点：门后那个 90° 转没有余量可切——影壁正对宅门，
                    # 只能沿走道先向西绕到中轴，再北进（文献：进门迎面影壁，向西经屏门入内院）。
                    # 过渡点属坐标层，不进图谱、不标站名。
                    path.append({"x": gate_x, "z": round(z_in, 3), "y": 0.0,
                                 "label": f"进入{name}"})
                    path.append({"x": round(r, 3), "z": round(z_in, 3), "y": 0.0})
                    path.append({"x": 0.0, "z": round(z_in + r, 3), "y": 0.0, "label": "折向中轴"})
                else:
                    path.append({"x": gate_x, "z": round(z_in, 3), "y": 0.0,
                                 "label": f"进入{name}"})
                    if abs(gate_x) > 0.01:
                        path.append({"x": 0.0, "z": round(z_in, 3), "y": 0.0, "label": "折向中轴"})
            else:
                path.append({"x": 0.0, "z": round(z_south - TOUR_OUTSIDE, 3), "y": 0.0,
                             "label": f"进入{name}"})

        # —— 庭心驻足：沿行进方向偏西轻扫一眼（不再朝西厢甩头 90°）——
        prev = path[-1]
        hdg = math.atan2(0.0 - prev["x"], z_court - prev["z"])
        path.append({"x": 0.0, "z": round(z_court, 3), "y": 0.0,
                     "label": f"{name}庭心", "pause": TOUR_PAUSE,
                     "look": _glance(0.0, z_court, hdg, -TOUR_LOOK_DEG, p["w"] / 2.0)})

        # —— 出下道门：由本院北界进入下一院；末院北面无门，止于北房之前 ——
        if i == last:
            nlabel = _label_of((p["bei"] or {}).get("role"), "院北", table=_tour_labels)
            z_stop = z_north - nd - 1.2 if nd > 0 else z_north - 1.2
            path.append({"x": 0.0, "z": round(z_stop, 3), "y": 0.0, "label": f"{nlabel}前",
                         "pause": TOUR_PAUSE, "look": [0.0, round(z_north, 3)]})
            path.append({"x": 0.0, "z": round(z_stop + 0.7, 3), "y": 0.0, "label": "游毕",
                         "pause": TOUR_END_PAUSE,
                         "look": _glance(0.0, z_stop + 0.7, 0.0, +TOUR_LOOK_DEG, p["w"] / 2.0)})
        elif enc.get("beimen"):
            path.append({"x": 0.0, "z": round(z_north - TOUR_DOOR_DEPTH_HALF, 3), "y": 0.0,
                         "label": "垂花门前", "pause": TOUR_PAUSE,
                         "look": [0.0, round(z_north + 2.0, 3)]})
            path.append({"x": 0.0, "z": round(z_north, 3), "y": TOUR_STEP, "label": "穿过垂花门"})
        elif (p["bei"] or {}).get("chuantang"):
            # 与图谱「过厅(passage)」节点同源：正房明间南北贯通，是内院↔后院之间的载体(非门)。
            # 巡游显式为两道门三段：内院 →(南门·明间)→ 过厅 →(北门·穿堂)→ 后院，
            # 与图谱过厅节点的「第一道门·南门(明间) / 第二道门·北门(穿堂)」完全对齐。
            # 坐标与改动前完全一致(仅补语义标签与驻足)，零穿实体结论不受影响。
            nm = p["bei"] or {}
            # 穿堂正房即过厅(guoting)，与图谱 passage 节点同义；图谱不区分是否 tingfangyuan，统一标「过厅」。
            hall = _label_of(nm.get("usage"), "过厅", table=_tour_labels)
            next_name = plotted[i + 1]["c"].get("name") or f"第{i + 2}进" if i + 1 < len(plotted) else ""
            # 第一道门：南门(明间)——从内院进过厅（落脚台基面，避免踩墙/门槛）
            path.append({"x": 0.0, "z": round(z_north - nd, 3), "y": TOUR_STEP,
                         "label": f"南门(明间)·进{hall}", "pause": TOUR_PAUSE,
                         "look": [0.0, round(z_north - nd / 2.0, 3)]})
            # 过厅（明间穿堂）过渡点：穿行其间
            path.append({"x": 0.0, "z": round(z_north - nd / 2.0, 3), "y": TOUR_STEP,
                         "label": f"{hall}"})
            # 第二道门：北门(穿堂)——出过厅达后院
            path.append({"x": 0.0, "z": round(z_north, 3), "y": TOUR_STEP,
                         "label": f"北门(穿堂)·出到{next_name}", "pause": TOUR_PAUSE,
                         "look": [0.0, round(z_north + 2.0, 3)]})
        else:
            path.append({"x": 0.0, "z": round(z_north - TOUR_DOOR_DEPTH_HALF, 3), "y": 0.0,
                         "label": "院北门前"})
            path.append({"x": 0.0, "z": round(z_north, 3), "y": TOUR_STEP, "label": "穿过院北门"})
    return path


def _geo_slab(role, cx, cy, cz, w, h, d):
    """单块板状构件（地面/屋顶/单面墙）。"""
    return {"role": role,
            "center": {"x": round(cx, 3), "y": round(cy, 3), "z": round(cz, 3)},
            "size": {"w": round(w, 3), "h": round(h, 3), "d": round(d, 3)}}


def _geo_base_edge_ring(base_role, cx, cy, cz, W, H, D, norms=None):
    """台基：周边阶条石边梁（满高）+ 中心填土顶面（仅顶面一层），返回构件清单。

    对应 dict「台基」form.build = edgeRingWithCoreTop：真实台基是「石边压土面」，
    外侧只见石边、顶面为可行走土面。实心满铺会让台基体素数超过建筑本体
    （正房实测 3630 vs 2253），故按此构造拆分。

    「边梁厚几格 / 顶面几层」是【造型层 ⑤】的实现参数（VOX 格的倍数），
    **不写入知识包**、④ 不感知——换 B-rep 引擎时本函数整体替换即可。
    构件 key 从 norms.room 读，知识包用不同 key 时此处无需改代码。
    """
    # 边梁厚 = 2 格（沿外轮廓一圈）；中心顶面 = 1 层。
    edge_t = VOXEL_SIZE * 2
    core_t = VOXEL_SIZE * 1
    if W <= 2 * edge_t or D <= 2 * edge_t:
        # 台面太小，挖空会碎掉 —— 退化为实心一块
        return [_geo_slab(base_role, cx, cy, cz, W, H, D)]
    inner_w = W - 2 * edge_t
    inner_d = D - 2 * edge_t
    return [
        # 四条边梁（满高）：南北通长、东西居中段，避免四角重复计
        _geo_slab(base_role, cx, cy, cz + (D - edge_t) / 2, W, H, edge_t),                  # 北
        _geo_slab(base_role, cx, cy, cz - (D - edge_t) / 2, W, H, edge_t),                  # 南
        _geo_slab(base_role, cx + (W - edge_t) / 2, cy, cz, edge_t, H, inner_d),             # 东
        _geo_slab(base_role, cx - (W - edge_t) / 2, cy, cz, edge_t, H, inner_d),             # 西
        # 中心填土顶面：仅顶面一层，位于台基顶（cy + H/2 之下 core_t 厚）
        _geo_slab(base_role, cx, cy + H / 2 - core_t / 2, cz, inner_w, core_t, inner_d),
    ]


def _geo_room(role, cx, cz, W, H, D, open_side=None, norms=None, spec=None):
    """房间 = 台基(或地面) + 屋顶 + 四壁（朝庭院一侧留门洞，而非整面掏空），内部空心。

    ④ 本职：把房间拆成可独立体素化的子构件，而非塞一整个实心长方体。
    open_side ∈ {'N','S','E','W'} 或其列表：该侧（们）朝庭院，墙面居中留门洞。
    传列表（如 ['S','N']）可表达「贯通门道」：南北双向开口。
    墙/顶厚度 t 取自 norms.room.thickness（原代码常量 WALL_THICKNESS）。

    底部构件：若 norms.<role>.taiming 已声明（＝知识包声明该角色有台基），则生成
    `norms.room.baseRole` 所指的底部构件（知识包当前指向台基）——台明高取其值、自墙面线
    外扩 norms.room.taimingOutset；未声明则回落为「该建筑自身 role 的地面」。
    （原「地面」是 dict.构件 里没有的构件名，改判为台基后台基与图谱构件表自洽；
      baseRole 原为代码里的 "taiji" 字面量，现由知识包声明。）
    """
    t = float(_norms_get(norms, ("room", "thickness"), "房间墙/顶/地厚"))
    tm = _spec_get(spec, norms, role, "taiming")
    if tm:
        tm = float(tm)
        outset = float(_norms_get(norms, ("room", "taimingOutset"), "台基外扩"))
        base_role = _norms_get(norms, ("room", "baseRole"), "房间底部构件角色")
        # 台基构造（知识包 dict 声明 build=edgeRingWithCoreTop）：周边阶条石边梁满高，
        # 中心填土只留顶面一层——真实台基本就是「石边压土面」，且实心满铺会让体素量
        # 超过建筑本体。边梁厚度/顶面层数是【造型层实现参数】，不入知识包。
        _geo_base_parts = _geo_base_edge_ring(base_role, cx, tm / 2, cz,
                                            W + 2 * outset, tm, D + 2 * outset, norms)
    else:
        tm = t
        _geo_base_parts = [_geo_slab(role, cx, t / 2, cz, W, t, D)]  # 无台基：回落为地面
    floor_top = tm
    roof_bot = H - t

    wall_h = roof_bot - floor_top                       # 墙高（地面顶 -> 屋顶底）
    y_wall = (floor_top + roof_bot) / 2                 # 墙竖向中点（floor_top=t 时即 H/2）
    open_set = {open_side} if isinstance(open_side, str) else set(open_side or [])
    comps = [
        *_geo_base_parts,                                          # 台基：边梁 + 中心顶面
        _geo_slab(role, cx, H - t / 2, cz, W, t, D),            # 屋顶
    ]
    if "N" not in open_set:
        comps.append(_geo_slab(role, cx, y_wall, cz + D / 2 - t / 2, W, wall_h, t))   # 北墙
    if "S" not in open_set:
        comps.append(_geo_slab(role, cx, y_wall, cz - D / 2 + t / 2, W, wall_h, t))   # 南墙
    if "E" not in open_set:
        comps.append(_geo_slab(role, cx + W / 2 - t / 2, y_wall, cz, t, wall_h, D))   # 东墙
    if "W" not in open_set:
        comps.append(_geo_slab(role, cx - W / 2 + t / 2, y_wall, cz, t, wall_h, D))   # 西墙
    # sorted()：set 的遍历顺序受字符串哈希随机化影响，会导致「同一份代码跑两次构件顺序不同」，
    # 破坏零漂移核验与产物可复现性。几何结果与顺序无关，此处仅固定顺序。
    for s in sorted(open_set):
        comps.extend(_geo_front_wall(role, cx, cz, W, H, D, t, wall_h, floor_top, roof_bot, s, norms))
    # 入口踏步：仅在有台面高差（floor_top > 0，即知识包声明了台明）时生成，
    # 落在与该侧门洞同中轴的位置（s 由 open_set 给，与 _geo_front_wall 同一侧）。
    comps.extend(_geo_entry_steps(role, cx, cz, W, D, t, floor_top, s_open=open_set, norms=norms))
    return comps


def _geo_entry_steps(role, cx, cz, W, D, wall_t, floor_top, s_open=(), norms=None):
    """朝庭院各侧的入口踏步：自院子地面(y=0)逐级抬升至台面(floor_top)。

    分层铁律：语义（构件 key）与规制（单级高/宽/进深/两侧留空）全部来自知识包
    norms.room.step*，本层只按声明值落体素——不含任何建筑角色名或造型决策。
    级数 = ceil(台面高 / 单级高)，每级等高、总高恰为台面（两侧留空量由 stepSideClear 声明，各级平齐）。
    """
    if floor_top <= 0:
        return []
    rise = _norms_get(norms, ("room", "stepRise"), "踏步单级高")
    tread = _norms_get(norms, ("room", "stepTread"), "踏步单级进深")
    width = _norms_get(norms, ("room", "stepWidth"), "踏步单级宽")
    side_clear = _norms_get(norms, ("room", "stepSideClear"), "踏步两侧收进")
    step_role = _norms_get(norms, ("room", "stepRole"), "踏步构件 key")
    rise = float(rise); tread = float(tread)
    width = float(width); side_clear = float(side_clear)
    if rise <= 0 or tread <= 0 or width <= 0:
        return []
    n = int(math.ceil(floor_top / rise - 1e-9))
    if n <= 0:
        return []
    out = []
    for k in range(n):
        # 每级高按【前 k 级之和已达的位置】与【剩余高度】均分，而非 floor_top/n：
        # 后者除不尽时（如 0.32/3）末级顶面会差 ~1mm，累计不上台面。
        y_bot = floor_top * (n - 1 - k) / n       # 本级底面高度（k=0 贴墙端即最高级，顶面=台面）
        y_top = floor_top * (n - k) / n           # 本级顶面高度（k=n-1 贴院子端即最低级，顶面=单级高）
        h = y_top - y_bot
        w = width - 2 * side_clear                # 两侧留空（固定值，非逐级收进——垂带踏跺各级平齐）
        if w <= 0 or h <= 0:
            break
        y = (y_bot + y_top) / 2                   # 本级竖向中点
        # 自该侧墙外皮（|cz| + D/2）起，向外逐级伸出：第 k 级占据 k*tread 起的一段
        run = tread * (k + 0.5)                   # 第 0 级贴墙，故偏移半个进深
        for s in sorted(s_open):                  # 只在朝庭院的开口侧生成
            if s == "N":
                out.append(_geo_slab(step_role, cx, y, cz + D / 2 + run, w, h, tread))
            elif s == "S":
                out.append(_geo_slab(step_role, cx, y, cz - D / 2 - run, w, h, tread))
            elif s == "E":
                out.append(_geo_slab(step_role, cx + W / 2 + run, y, cz, tread, h, w))
            else:  # W
                out.append(_geo_slab(step_role, cx - W / 2 - run, y, cz, tread, h, w))
    return out


def _geo_gate_tower(role, cx, cz, W, base_h, top_h, D, norms=None):
    """门楼：坐落在门道屋顶之上的一段抬高墙冠 + 顶，使宅门明显高于倒座房。

    ④ 本职：门楼是独立子构件，纯几何；⑤ 实心体素化即可。
    base_h=门道屋顶高，top_h=门楼屋顶高（均来自 norms），band=抬高的墙冠。
    """
    if top_h <= base_h:
        return []
    t = float(_norms_get(norms, ("room", "thickness"), "门楼壁厚"))
    band = top_h - base_h
    yc = (base_h + top_h) / 2
    comps = [
        _geo_slab(role, cx, top_h - t / 2, cz, W, t, D),       # 门楼顶
    ]
    comps.append(_geo_slab(role, cx, yc, cz + D / 2 - t / 2, W, band, t))   # 南壁冠
    comps.append(_geo_slab(role, cx, yc, cz - D / 2 + t / 2, W, band, t))   # 北壁冠
    comps.append(_geo_slab(role, cx + W / 2 - t / 2, yc, cz, t, band, D))   # 东壁冠
    comps.append(_geo_slab(role, cx - W / 2 + t / 2, yc, cz, t, band, D))   # 西壁冠
    return comps


def _geo_front_wall(role, cx, cz, W, H, D, t, wall_h, floor_top, roof_bot, open_side, norms=None):
    """朝庭院的墙：居中留门洞（宽/高取自 norms.door.*），由左右墙段+门楣组成。

    左右墙段为整高实体，门洞上方用门楣封顶；门洞本身不生成体素（即门）。
    """
    face_span = W if open_side in ("N", "S") else D
    dw = min(float(_norms_get(norms, ("door", "width"), "房门洞宽")), face_span - 2 * t)   # 门洞宽（不超过墙面净宽）
    dh = min(float(_norms_get(norms, ("door", "height"), "房门洞高")), wall_h)             # 门洞高
    lx = dw / 2
    door_top = floor_top + dh
    lintel_h = roof_bot - door_top
    y_lintel = (door_top + roof_bot) / 2
    y_wall = (floor_top + roof_bot) / 2                    # 墙竖向中点（floor_top=t 时即 H/2）
    out = []
    if open_side in ("N", "S"):
        z = cz + (D / 2 - t / 2) if open_side == "N" else cz - (D / 2 - t / 2)
        seg = W / 2 - lx                                  # 单侧墙段宽
        out.append(_geo_slab(role, cx - (lx + seg / 2), y_wall, z, seg, wall_h, t))   # 左墙段
        out.append(_geo_slab(role, cx + (lx + seg / 2), y_wall, z, seg, wall_h, t))   # 右墙段
        if lintel_h > 0:
            out.append(_geo_slab(role, cx, y_lintel, z, dw, lintel_h, t))            # 门楣
    else:  # E / W
        x = cx + (W / 2 - t / 2) if open_side == "E" else cx - (W / 2 - t / 2)
        seg = D / 2 - lx                                  # 单侧墙段深
        out.append(_geo_slab(role, x, y_wall, cz - (lx + seg / 2), t, wall_h, seg))   # 左墙段
        out.append(_geo_slab(role, x, y_wall, cz + (lx + seg / 2), t, wall_h, seg))   # 右墙段
        if lintel_h > 0:
            out.append(_geo_slab(role, x, y_lintel, cz, t, lintel_h, dw))            # 门楣
    return out


def _geo_house(node, cx, W, D, zc, open_side, norms, applied):
    """一栋房屋（北/南/东/西任一朝向）：按**图谱声明 + 知识包形体声明**分派。

    代码不认任何角色名，只看节点声明了什么：
      · 节点带 `gate`（声明了嵌在它身上的门）→ 带门道的房屋（门道落哪端由门的 form.at 给）
      · 节点带 `chuantang: true`            → 明间前后贯通的房屋
      · 其余                                → 普通房间（朝院一侧留门洞）

    原先是三个按角色名硬判的分支（_geo_wing / _geo_daozuo / _geo_back_gate），
    现已收成一个通用入口——「后门在西北角、宅门在东南角」这类事实全在知识包。"""
    role = node.get("role")
    H = _role_height(norms, role, node)
    gate = node.get("gate")
    gate_role = gate.get("role") if isinstance(gate, dict) else None
    if gate_role:
        gf = _form_of(applied, gate_role)
        if gf.get("kind") != "gate-passage":
            raise ValueError("图谱缺陷：门 %r 的形体原型应为 gate-passage，实际 %r"
                             % (gate_role, gf.get("kind")))
        return _geo_gate_house(cx, W, D, zc, node, gate_role, open_side, norms, gf)
    if node.get("chuantang"):
        return _geo_chuantang(cx, W, D, zc, node, norms)
    return _geo_room(role, cx, zc, W, H, D, open_side, norms, node)


def _geo_gate_house(cx, W, D, zc, node, gate_role, open_side, norms, gate_form):
    """带门道的房屋：整排房拆成「一段普通房间 + 一端门道间(± 门楼)」。

    门道落在哪一端由知识包声明（`gate_form["at"]`），代码只按 at 做通用摆放：
      east-end → 门道贴东端、留 margin 白  ；west-end → 贴西端、留 margin 白
    是否带门楼由 `gate_form["tower"]` 声明；数值（面阔/高/留白）取自 norms.<门角色>。

    这就是「宅门在东南角、后门在西北角」这两条风格的**唯一事实源**——
    原先它们是 _geo_daozuo / _geo_back_gate 两个函数里的加减号。
    """
    role = node.get("role")
    room_h = _role_height(norms, role, node)
    at = gate_form.get("at")
    if at not in ("east-end", "west-end"):
        raise ValueError("图谱缺陷：门 %r 的 form.at=%r 不能嵌在房屋上（只支持 "
                         "east-end / west-end；居中的门用 beimen/nanmen 槽位）" % (gate_role, at))
    gs = round(min(float(_norms_get(norms, (gate_role, "gateSpan"), "门道面阔")), W - 0.6), 3)
    margin = float((norms.get(gate_role) or {}).get("margin", 0.0))
    sign = 1.0 if at == "east-end" else -1.0
    gate_center = round(cx + sign * (W / 2 - gs / 2 - margin), 3)
    # 剩余段（门道之外的那一段普通房间）
    a, b = cx - W / 2, cx + W / 2
    lo, hi = (a, gate_center - gs / 2) if at == "east-end" else (gate_center + gs / 2, b)
    comps = list(_geo_room(role, round((lo + hi) / 2, 3), zc, round(hi - lo, 3), room_h, D,
                           open_side, norms, node))
    # 门道：南北贯通（临街 ↔ 院内），高 = 同排普通房高
    comps.extend(_geo_room(gate_role, gate_center, zc, gs, room_h, D, ["S", "N"], norms))
    if gate_form.get("tower"):
        gh = float(_norms_get(norms, (gate_role, "height"), "门楼高"))
        comps.extend(_geo_gate_tower(gate_role, gate_center, zc, gs, room_h, gh, D, norms))
    return comps


def _geo_chuantang(cx, W, D, zc, node, norms):
    """明间（中央开间）前后贯通的做法：拆成「左右尽间(朝院内开敞) + 中央明间(南北贯通门道)」。

    ④ 本职：把该栋拆成 3 个开间子构件；⑤ 实心体素化即可。
    门道方向由图谱的 `chuantang` 标记驱动（不认角色名）。
    """
    role = node.get("role")
    if not role:
        raise ValueError("图谱缺陷：声明 chuantang 的建筑缺 role（穿堂是某栋的做法，不是独立对象）")
    H = _role_height(norms, role, node)
    miankuo = _dim(node, "miankuo", 0)
    bay = (W / miankuo) if miankuo else W            # 每间面阔(米)
    central = min(bay, W * 0.4)                      # 中央明间，作穿堂
    side = (W - central) / 2
    comps = []
    if side > 0.2:
        comps.extend(_geo_room(role, cx - (central / 2 + side / 2), zc, side, H, D, "S", norms, node))
        comps.extend(_geo_room(role, cx + (central / 2 + side / 2), zc, side, H, D, "S", norms, node))
    comps.extend(_geo_room(role, cx, zc, central, H, D, ["S", "N"], norms, node))
    return comps


def _wing_length(node, norms, d, nd, sd, modus):
    """沿庭院方向(Z)长度：读 `rules.norms.layout.wing` 约束，尊重图谱声明的开间数。

    - lengthMode=miankuo：长度取自身面阔(间数×modus)，即知识包声明的开间数
    - aisle：仅当院净深足以容纳「满间 + 两侧通道」时才保留；院偏浅时不再无条件扣 2×aisle，
      只按院净深封顶防与南北房重叠，多余空间自动成为通道（不压厢房开间）
    - zAlign=center 由调用方（ew_z = 庭院净深中心）实现
    """
    layout = _norms_get(norms, ("layout", "wing"), "翼房布局约束（lengthMode/aisle/zAlign）")
    aisle = float(layout.get("aisle", 0))
    own = float(_dim(node, "miankuo", 0)) * modus     # 自身面阔(间数×modus)
    court_net = d - nd - sd                           # 庭院净深
    # 厢房绝不顶到南北房/院墙：两端各留 aisle 通道（传统由抄手游廊/耳房接过去）；
    # 院净深不足时按净深封顶，声明开间可能被压短——窄院本就短翼，属合理，但口子必须留。
    return round(min(own, court_net - 2 * aisle), 3)


def _geo_gate_standalone(role, cz, norms, form):
    """独立门屋（不挂在任何建筑上的门本体，如卡子墙正中的垂花门）。

    ④ 本职：门道为围合结构(南北开门)，门楼（若声明）为独立子构件；⑤ 实心体素化即可。
    面阔 gs 取自 norms.<role>.gateSpan，与 _geo_wall_ring 在该侧开洞同源，
    保证「门体宽 == 墙洞口宽」，两侧不留通缝。
    """
    gs = round(float(_norms_get(norms, (role, "gateSpan"), "门道面阔")), 3)
    depth = float(_norms_get(norms, (role, "depth"), "门道进深"))
    base_h = float(_norms_get(norms, ("room", "heightDefault"), "门道基准高"))
    comps = list(_geo_room(role, 0, cz, gs, base_h, depth, ["S", "N"], norms))   # 门道南北贯通
    if form.get("tower"):
        gh = round(float(_norms_get(norms, (role, "height"), "门楼高")), 3)
        if gh > base_h + 0.05:
            comps.extend(_geo_gate_tower(role, 0, cz, gs, base_h, gh, depth, norms))   # 门楼略高
    return comps


def _geo_colonnade(role, w, nd, zc, d, norms):
    """柱廊（形体原型 colonnade）：柱列 + 廊顶，通透无实墙。

    【当前不启用】各进 peripheral 未声明该形体，故本函数暂不产生体素；
    留待「加细节」阶段确定形制与归属后，在知识包 peripheral 里声明即可启用（代码零改动）。

    廊与院墙不同：不围合，只提供有顶通道。中轴穿堂口按 norms.door.width 断开，
    让出明间南北通行的门道（否则就成了堵在正房前的一堵墙）。
    尺寸全部取自 norms.peripheral.<role>。
    """
    cfg = _norms_get(norms, ("peripheral", role), "%s 尺寸（形体参数）" % role)
    H = float(cfg["height"])
    depth = float(cfg["depth"])
    span_ratio = float(cfg["spanRatio"])
    col_spacing = float(cfg["colSpacing"])
    top_h = float(cfg["roofThickness"])
    col = float(_norms_get(norms, ("room", "thickness"), "廊柱截面"))
    gap = float(_norms_get(norms, ("door", "width"), "穿堂口宽"))
    out = []
    zpos = zc + d / 2 - nd - depth / 2
    half = (w * span_ratio) / 2.0
    for a, b in ((-half, -gap / 2.0), (gap / 2.0, half)):    # 左右两段，中间让开穿堂
        seg = b - a
        if seg <= 0.05:
            continue
        out.append(_geo_slab(role, (a + b) / 2.0, H - top_h / 2.0, zpos, seg, top_h, depth))
        n = max(2, int(round(seg / col_spacing)) + 1)         # 柱列：两端 + 按 colSpacing 均布
        for i in range(n):
            x = a + seg * i / (n - 1)
            out.append(_geo_slab(role, x, (H - top_h) / 2.0, zpos, col, H - top_h, col))
    return out


def _geo_screen_wall(role, w, sd, zc, d, norms):
    """独立屏墙（形体原型 screen-wall，如影壁）。尺寸取自 norms.peripheral.<role>。"""
    cfg = _norms_get(norms, ("peripheral", role), "%s 尺寸（形体参数）" % role)
    bw, H, thick = float(cfg["width"]), float(cfg["height"]), float(cfg["depth"])
    zpos = zc - d / 2 + sd + float(cfg["zOffset"])
    return {"role": role,
            "center": {"x": round(w / 2 - bw / 2 - float(cfg["xInset"]), 3),
                       "y": H / 2, "z": round(zpos, 3)},
            "size": {"w": bw, "h": H, "d": thick}}


def _geo_wall(cx, cz, width_x, H, depth_z, role):
    """单段墙：宽沿 X(width_x)，厚沿 Z(depth_z)。"""
    return {"role": role,
            "center": {"x": round(cx, 3), "y": H / 2, "z": round(cz, 3)},
            "size": {"w": round(width_x, 3), "h": H, "d": round(depth_z, 3)}}


def _geo_wall_ring(c, w, zc, d, norms, applied, draw_south=True, wall_kinds=None,
                   ring_kinds=None, wall_role=None):
    """院墙环：先实例化「完整一圈墙」，不预判任何建筑位置（boundarySegmentRealization）。
    - 北/南按 gate 开缺：门道落哪端、多宽，全读**门的 form（at）+ norms.<门角色>**，
      代码里不出现任何门角色名（原先是一串 `gate == "zhaimen"/"chuihuamen"/"houmen"`）。
    - 东西墙先画整段；贴边建筑（后檐墙/山墙）的占位由 _resolve_boundary 统一去重。
    - 每进只承担自己的北界；整院南外墙仅由最南一进(idx0)承担。
    - 墙高/厚按墙种取：该侧 ring.<side>.kind 属「基底院墙」类（appliedRules.wall.taxonomy
      里 appliesTo=ringBase 的组）时，取 appliedRules.wall.kinds[kind] 的 height/thickness；
      否则回落 norms.wall。**houyanqiang 属建筑用墙**，其 thickness(0.3) 是建筑后檐墙的、
      不是院墙的，用在基底院墙上会在被 _resolve_boundary 部分替换后残留出薄墙。
    """
    ring = c.get("ring", {}) or {}
    t = float(_norms_get(norms, ("room", "thickness"), "墙面线偏移基准（取房间墙厚）"))

    def side_h_t(side):
        """该侧墙种 -> (H, T)；非「基底院墙」类、或该 kind 无声明，即回落 norms.wall。"""
        kind = (ring.get(side) or {}).get("kind")
        spec = (wall_kinds or {}).get(kind) if (kind and kind in (ring_kinds or set())) else None
        if not isinstance(spec, dict):
            spec = {}
        h, th = spec.get("height"), spec.get("thickness")
        H = float(h) if h is not None else float(_norms_get(norms, ("wall", "height"), "院墙高"))
        T = float(th) if th is not None else float(_norms_get(norms, ("wall", "thickness"), "院墙厚"))
        return H, T

    half = w / 2 - t / 2                     # 东西墙中心 X（与厢房外墙同一墙面线）
    # 北/南院墙中心 = 建筑后檐墙中心(zN - t/2 / zS + t/2)，而非院边界 zN/zS：
    # 建筑墙以 footprint 边为外皮、中心内缩 t/2（_geo_slab 各处 cz ± D/2 ∓ t/2），
    # 若院墙中心取院边界 zN，则两者错开 t/2=0.15 > _resolve_boundary 的 0.1 共线容差，
    # 被判成两条墙互不相减 → 院墙压住建筑墙(吃墙) + 角部留 0.15 缝。对齐中心后即可正确去重。
    zN = zc + d / 2 - t / 2                 # 北院墙中心 = 北房后檐墙中心
    zS = zc - d / 2 + t / 2                 # 南院墙中心 = 南房后檐墙中心
    out = []

    def ns_wall(zc_wall, gate, side):
        H, T = side_h_t(side)
        if not gate:
            out.append(_geo_wall(0, zc_wall, w, H, T, wall_role))
            return
        # 门洞宽 = 门体面阔(gateSpan)，与 _geo_gate_house / _geo_gate_standalone 同源，
        # 保证「门体宽 == 墙洞口宽」，两侧不留通缝。
        gs = float(_norms_get(norms, (gate, "gateSpan"), "%s 门道面阔" % gate))
        ghalf = gs / 2
        at = _form_of(applied, gate).get("at") or "center"
        margin = float((norms.get(gate) or {}).get("margin", 0.0))
        if at == "east-end":
            gx = round(w / 2 - gs / 2 - margin, 3)
        elif at == "west-end":
            gx = round(-(w / 2 - gs / 2 - margin), 3)
        elif at == "center":
            gx = 0.0
        else:
            raise ValueError("图谱缺陷：门 %r 的 form.at=%r 非法（东端 east-end / 西端 "
                             "west-end / 居中 center）" % (gate, at))
        l_seg = (gx - ghalf) - (-half)
        if l_seg > 0.01:
            out.append(_geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, wall_role))
        r_seg = half - (gx + ghalf)
        if r_seg > 0.01:
            out.append(_geo_wall((gx + ghalf) + r_seg / 2, zc_wall, r_seg, H, T, wall_role))

    # 北墙：本进与后一进的分界（最北一进的北墙 = 整院北外墙）
    ns_wall(zN, (ring.get("bei") or {}).get("gate"), "bei")
    # 南墙：仅最南一进(idx0)画 —— 即整院南外墙；其余进的南界由前一进北墙承担
    if draw_south:
        ns_wall(zS, (ring.get("nan") or {}).get("gate"), "nan")
    # 东西墙：先画整段；贴边建筑的占位由 _resolve_boundary 统一去重
    Hd, Td = side_h_t("dong")
    out.append(_geo_wall(half, zc, Td, Hd, d, wall_role))
    Hx, Tx = side_h_t("xi")
    out.append(_geo_wall(-half, zc, Tx, Hx, d, wall_role))
    return out


def _resolve_boundary(components, norms, wall_role):
    """边界墙去重（boundarySegmentRealization 的几何实现）。

    同一条共线墙线上，建筑墙(后檐墙/山墙, pri=1)优先于独立院墙(wall_role, pri=0)：
    把被建筑覆盖的区间从独立院墙段中【区间相减】掉（非整段删），保留真正空档。

    建筑自身的门/窗洞口（由矮薄的门楣标记，见 _geo_front_wall）一并算作「建筑覆盖段」——
    洞口是建筑的开口，独立院墙不得残留在洞口中（否则会把穿堂/门洞堵死）。
    resolver 只看真实几何覆盖，不预判任何建筑位置——增删建筑时该侧院墙自动补/让。
    wall_role = appliedRules.wall.ref（独立院墙的空间角色 key），不再硬编字面量。
    """
    thin = float(_norms_get(norms, ("room", "thickness"), "细墙/门楣判定基准")) + 0.15   # +0.15 为几何容差，非规制值
    walls = []                                    # [orient, line, lo, hi, pri, idx]
    holes_extra = []                              # [orient, line, lo, hi] 洞口(门楣)区间
    for i, g in enumerate(components):
        s = g.get("size", {}) or {}
        c = g.get("center", {}) or {}
        w, h, d = s.get("w", 0), s.get("h", 0), s.get("d", 0)
        if min(w, d) > thin:                      # 宽块：地面/屋顶/门楼顶等，非墙
            continue
        if w < d:                                 # 南北向构件(沿 Z)，线=x
            orient, line = "V", c.get("x", 0)
            lo, hi = c.get("z", 0) - d / 2, c.get("z", 0) + d / 2
        else:                                     # 东西向构件(沿 X)，线=z
            orient, line = "H", c.get("z", 0)
            lo, hi = c.get("x", 0) - w / 2, c.get("x", 0) + w / 2
        if h <= 1.5:                              # 矮薄块 = 门楣(洞口顶)：记录该洞口区间
            if g.get("role") != wall_role:
                holes_extra.append([orient, line, lo, hi])
            continue
        pri = 0 if g.get("role") == wall_role else 1
        walls.append([orient, line, lo, hi, pri, i])

    groups = {}
    for wl in walls:                              # 按共线(容差 0.1m)分组
        groups.setdefault((wl[0], round(wl[1], 1)), []).append(wl)
    extra_groups = {}
    for lt in holes_extra:
        extra_groups.setdefault((lt[0], round(lt[1], 1)), []).append((lt[2], lt[3]))

    dropped, extra = set(), []
    for key, segs in groups.items():
        ivs = [(s[2], s[3]) for s in segs if s[4] == 1] + extra_groups.get(key, [])
        high = _merge_ivs(ivs)                               # 建筑覆盖段(含门窗洞口) = 洞
        for s in segs:
            if s[4] != 0:                                     # 建筑段原样保留
                continue
            pieces = [(s[2], s[3])]
            for a, b in high:                                 # 逐洞区间相减
                nxt = []
                for p0, p1 in pieces:
                    if b <= p0 + 1e-6 or a >= p1 - 1e-6:
                        nxt.append((p0, p1)); continue
                    if a > p0 + 1e-6:
                        nxt.append((p0, a))
                    if b < p1 - 1e-6:
                        nxt.append((b, p1))
                pieces = nxt
            comp = components[s[5]]
            if not pieces:
                dropped.add(s[5]); continue                   # 整段被建筑覆盖
            if (len(pieces) == 1 and abs(pieces[0][0] - s[2]) < 1e-6
                    and abs(pieces[0][1] - s[3]) < 1e-6):
                continue                                      # 未被切，原样
            for k, (p0, p1) in enumerate(pieces):             # 首段改写原构件，其余新增
                nc = {"role": comp["role"],
                      "center": dict(comp["center"]),
                      "size": dict(comp["size"])}
                if s[0] == "V":
                    nc["center"]["z"] = round((p0 + p1) / 2, 3)
                    nc["size"]["d"] = round(p1 - p0, 3)
                else:
                    nc["center"]["x"] = round((p0 + p1) / 2, 3)
                    nc["size"]["w"] = round(p1 - p0, 3)
                if k == 0:
                    components[s[5]] = nc
                else:
                    extra.append(nc)
    return [components[i] for i in range(len(components)) if i not in dropped] + extra


def _merge_ivs(ivs):
    """合并重叠/相接的区间：把建筑墙段与其门楣洞口并成连续的「建筑覆盖段」。"""
    out = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out



# ---------------- ⑤ 几何造型引擎：构件 -> 体素 BOX 清单 ----------------
def _voxelize_component(g, vox, labels, colors):
    """构件(连续几何) -> 体素 BOX 网格（构件 : box = 图像 : 像素）。

    纯几何转换：把传入的构件实心切成边长为 vox 的体素网格。构件本身是实心还是
    空心围合（如房间拆成的墙/顶/地子构件），由 ④ 几何计算引擎决定，⑤ 不过问。
    label / color 均取自命名字典快照（两张表由调用方一次取好，逐构件复用）；
    color 由所属构件继承（点选任意体素都能识别其构件）。
    表里缺该 role 即报图谱缺陷——图示色与中文名都是知识事实，代码不兜底。
    """
    role = g.get("role")
    c = g.get("center", {})
    s = g.get("size", {})
    W, H, D = s.get("w", 0), s.get("h", 0), s.get("d", 0)
    if W <= 0 or H <= 0 or D <= 0:
        return []
    nx = max(1, int(round(W / vox)))
    ny = max(1, int(round(H / vox)))
    nz = max(1, int(round(D / vox)))
    sx, sy, sz = W / nx, H / ny, D / nz          # 实际体素尺寸（精确贴合构件边界）
    x0 = c.get("x", 0) - W / 2
    y0 = c.get("y", 0) - H / 2
    z0 = c.get("z", 0) - D / 2
    label = _label_of(role, dflt=role, table=labels)
    if role not in colors:
        raise ValueError("图谱缺陷：dict.json 缺词条 %r 的 color —— 图示色属知识事实，"
                         "新增 role 须先在 dict.json 补 form/color" % (role,))
    color = colors[role]
    out = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                out.append({
                    "x": round(x0 + (i + 0.5) * sx, 3),
                    "y": round(y0 + (j + 0.5) * sy, 3),
                    "z": round(z0 + (k + 0.5) * sz, 3),
                    "w": round(sx, 3), "h": round(sy, 3), "d": round(sz, 3),
                    "role": role, "label": label, "color": color,
                })
    return out


def geometry_to_boxes(geometry, vox=VOXEL_SIZE, instance=None):
    """⑤ 几何造型引擎：构件 -> 体素 BOX 清单（真实多体素化，非 1 构件=1 box 占位）。

    选定 BOX 作为 MVP 表现基元，把每个构件按 VOXEL_SIZE 体素化成 box 网格。
    label / color 均取自命名字典快照（此处一次取表、逐构件复用）。
    未来切 B-rep 只改此处，④ 不动。
    """
    # 入参形状闸 + 出口兜底闸：同 compute_geometry，保持「绝不静默返回 []」这条不变式。
    # 实测静默路径有三个：[]（空清单）、{}（字典被当可迭代空转）、
    # [{"role":"zhengfang"}]（构件缺 size → _voxelize_component 对零尺寸构件返回 []）。
    # 零尺寸构件本身返回空是对的（它没有体积），但**整份算不出体素**必是入参缺陷。
    if not isinstance(geometry, list):
        raise ValueError("图谱缺陷：geometry_to_boxes 的入参须是 compute_geometry 输出的"
                         "构件清单（list），收到 %s" % type(geometry).__name__)
    if not geometry:
        raise ValueError("图谱缺陷：geometry_to_boxes 入参为空 —— 须先成功调用 "
                         "compute_geometry 拿到构件清单，再调本工具")
    if not all(isinstance(g, dict) for g in geometry):
        raise ValueError("图谱缺陷：geometry 清单里含非对象项（构件须是对象）")
    # ⑤ 中文名 / 图示色的唯一来源：实例图谱自带的 appliedDict 快照（自动化端不回读盘包）。
    # 独立调用未带 instance 时表为空——label 退化为 role key 显示，但 color 会 fail-fast
    # （缺知识时宁可不产出，也不静默涂一个假色）。
    applied = instance.get("appliedDict") if instance else None
    labels = _labels_from_applied(applied)
    colors = _colors_from_applied(applied)
    boxes = []
    for g in geometry:
        boxes.extend(_voxelize_component(g, vox, labels, colors))
    if not boxes:
        raise ValueError(
            "图谱缺陷：构件清单非空却算不出任何体素 —— 构件缺 center/size（零尺寸构件"
            "不产生体素），通常说明该清单不是 compute_geometry 的产出")
    return boxes


# ---------------- 串联入口（便捷：本地验证 ④⑤ 全链） ----------------
def instance_to_boxes(instance):
    """instance -> 体素 BOX 清单（④ -> ⑤ 串联）。

    仅作本地验证便捷口；生产路径（MCP generate_building）是分别调
    compute_geometry / geometry_to_boxes，以便在两步之间做各自的形状闸。
    """
    return geometry_to_boxes(compute_geometry(instance), instance=instance)
