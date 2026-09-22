"""
④ 几何计算引擎 + ⑤ 几何造型引擎(BOX 出口)
------------------------------------------------
输入 ：实例图谱工程文件（server/data/instances/*.json）
       自包含：data 块为实例数据（拓扑+尺度具体值），appliedRules 为规则快照。
       ④ 只读 instance 整体（data + appliedRules），不碰外部 dict.json / rules.json。
       ① 基线（build_instance）读知识中心（type.json + rules.json）合成 instance，供验证与落库；
       2.0 在线链路的 ① 归 Agent 侧（LLM 出骨架 → skill 的 assemble 装配），④ 不读外部知识文件。
输出 ：⑤ 体素 BOX 清单（场景坐标：Y-up，单位米）
       每个 box = {x,y,z, w,h,d, role, label, color}

分层（见 几何计算引擎IO契约.md）：
- build_instance(jin)        = ① 确定性基线：读 type+rules，按进数合成自包含 instance（供验证/落库）
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
import json
import math
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # server/
KNOWLEDGE_DIR = os.path.join(BASE, "knowledge")
DATA_DIR = os.path.join(BASE, "data", "instances")

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
VOXEL_SIZE = 0.6

# 中文名一律取自命名字典（dict.json）——⑤ 造型层与巡游路径都不再内置词表。
# 内置表必然与字典漂移，而且已经漂过一次：houmen 字典里有「后门」、内置表没有，
# ⑤ 于是把拼音 key 原样吐给前端（屏幕上直接显示 "houmen"）。
# 表按 dict.json 的 mtime 缓存：本地改字典立即生效，不会出现「改了不生效」的假象。
_DICT_LABELS = {"mtime": None, "flat": {}}


def _dict_labels():
    """dict.json -> 扁平 {key: 中文名}（跨类目合并；key 全库唯一，已核实无重名）。"""
    path = os.path.join(KNOWLEDGE_DIR, "dict.json")
    mt = os.path.getmtime(path)
    if _DICT_LABELS["mtime"] != mt:
        flat = {}
        for cat, items in load_json(path).items():
            if cat == "meta" or not isinstance(items, dict):
                continue
            for k, v in items.items():
                if isinstance(v, dict) and isinstance(v.get("label"), str):
                    flat[k] = v["label"]
        _DICT_LABELS.update(mtime=mt, flat=flat)
    return _DICT_LABELS["flat"]


def _label_of(key, dflt=None, table=None):
    """key -> 中文名（字典为准）。字典缺词条：给了 dflt 就回落，没给则报图谱缺陷
    —— 不静默把拼音 key 当成中文名吐出去（那正是漂移发生时的表现）。"""
    hit = (table if table is not None else _dict_labels()).get(key)
    if hit:
        return hit
    if dflt is not None:
        return dflt
    raise ValueError(
        "图谱缺陷：dict.json 缺词条 %r —— 中文名一律取自命名字典，"
        "新增 role/key 须先在 dict.json 补词条" % (key,))


ROLE_COLORS = {
    "zhengfang": 0xC0504D, "xiangfang": 0xE0A030, "daozuofang": 0x4F81BD,
    "houzhaofang": 0x9B59B6, "chuihuamen": 0x82A33A, "erfang": 0x9B59B6,
    "youlang": 0x808080, "yingbi": 0xB0A040, "tingyuan": 0xCFCFCF, "yuanqiang": 0x7F7F7F,
    "zhaimen": 0x8B4513, "taiji": 0x9E9284,
}

def _room(role, norms, type_doc=None):
    """一栋建筑的声明：role + 尺度 + 该栋自身的属性（等级 / 材质 / 高度 / 台明）。

    属性来源：规则库 norms.<role>（height / taiming）+ 类型图谱 roles.<role>
    （level / material）。属性「长在建筑上」而不只挂在 role 上——图谱是「这一座」的
    差量，同一 role 的不同栋可有不同取值；④ 读建筑自带的 height / taiming。
    """
    n = norms.get(role, {}) or {}
    t = ((type_doc or {}).get("roles") or {}).get(role, {}) or {}
    r = {"role": role,
         "miankuo": n.get("miankuo", 5),
         "jinshen": n.get("jinshen", 3),
         # 朝院门洞：各房门窗均向院内开辟，门在明间(正中开间)。
         # **开向不进图谱**——它由房屋所在侧推得（北房朝南、南房朝北、东厢朝西、西厢朝东），
         # 属几何事实；写进图谱就变成引擎级动作了。动线(liantong)据此声明「院↔房」可通。
         "door": {"at": "mingjian"}}
    for k in ("height", "taiming"):
        if n.get(k) is not None:
            r[k] = n[k]
    for k in ("level", "material"):
        if t.get(k) is not None:
            r[k] = t[k]
    return r


def _cy(seq, name, bei=None, nan=None, dong=None, xi=None,
        beimen=None, nanmen=None, peripheral=None, perimeter=False):
    enc = {"relation": "weihe"}
    if bei: enc["bei"] = bei
    if nan: enc["nan"] = nan
    if dong: enc["dong"] = dong
    if xi: enc["xi"] = xi
    if beimen: enc["beimen"] = beimen
    if nanmen: enc["nanmen"] = nanmen
    c = {"id": f"cy{seq}", "name": name, "sequence": seq,
         "enclosure": enc, "center": {"role": "tingyuan"}}
    if perimeter:
        c["perimeter"] = True
    if peripheral:
        c["peripheral"] = peripheral
    return c


# ④ 实际消费的 norms 路径前缀：appliedRules 只保留这些前缀下的整棵子树，其余裁掉。
# 来源：grep 全文件 _norms_get(norms, (...)) 与 norms.get(...) 汇总——
#   modus / courtDepthRatio（整体）
#   room.{thickness,taimingOutset,heightDefault} / door.{width,height}
#   zhaimen.{gateSpan,height,eastMargin} / houmen.{gateSpan,westMargin} / layout.xiangfang
#   chuihuamen.{gateSpan,height,depth} / peripheral.{youlang,yingbi} / wall.{height,thickness}
#   逐角色：zhengfang/xiangfang/daozuofang/houzhaofang 的 height & taiming
#           （zhaimen/chuihuamen 的 height 经 _role_height 回落读取，一并保留其整棵子树）
_NORMS_KEEP_PREFIXES = [
    ("modus",), ("courtDepthRatio",),
    ("room",), ("door",), ("zhaimen",), ("houmen",), ("layout",), ("chuihuamen",),
    ("peripheral",), ("wall",),
    ("zhengfang",), ("xiangfang",), ("daozuofang",), ("houzhaofang",),
]


def _keep_subtree(src, prefix):
    """从 norms 取 prefix 路径下的整棵子树；任一节点缺失则返回 None（该前缀本就不被此院用到）。"""
    cur = src
    for k in prefix:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _snapshot_rules(rules_doc):
    """规则库 -> appliedRules 快照：只保留 ④ 实际消费的 norms 子树，无关词条全裁。

    仍是深拷贝，instance 自包含、可脱离知识中心独立复现；但不再夹带 orientation / position /
    usage / sequence / wall 等 ④ 不读的整段规制与文字说明。裁错路径会被 _norms_get 的「缺失即报错」
    立刻暴露，所以裁剪是零风险 + 可验证的（每次改完跑零漂移复核）。
    """
    rules = rules_doc if isinstance(rules_doc, dict) else json.loads(json.dumps(rules_doc))
    full = rules.get("norms", {})
    if not isinstance(full, dict) or "modus" not in full:
        raise ValueError("图谱缺陷：siheyuan.rules 缺少 norms.modus")
    trimmed = {}
    for prefix in _NORMS_KEEP_PREFIXES:
        sub = _keep_subtree(full, prefix)
        if sub is None:
            continue
        d = trimmed
        for k in prefix[:-1]:
            d = d.setdefault(k, {})
        d[prefix[-1]] = sub
    return {"norms": trimmed}


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


def _jin_cond_ok(cond, jin):
    """规则库里 `when` 条件的求值（如 "jin>=4" / "jin==2" / None=恒真）。

    条件写在图谱里（业务语义），④ 只做通用求值，不把「四进院才有过厅」这类知识
    硬编码进代码。
    """
    if not cond:
        return True
    m = re.match(r"^\s*jin\s*(>=|<=|==|>|<)\s*(\d+)\s*$", str(cond))
    if not m:
        raise ValueError(f"图谱缺陷：rules 中无法求值的 when 条件「{cond}」")
    op, n = m.group(1), int(m.group(2))
    return {">=": jin >= n, "<=": jin <= n, "==": jin == n,
            ">": jin > n, "<": jin < n}[op]


def _used_terms(*docs):
    """收集若干图谱块里出现过的全部标量字符串值（用于裁剪命名字典：只带用到的词）。"""
    used = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            used.add(o)

    for d in docs:
        walk(d)
    return used


def _extract_dict(dict_doc, *docs):
    """命名字典子集：只保留被用到的词条（按类别裁剪）。

    判据同「附属只带用到的」——删掉任一条，图谱里就有解释不通的词。
    meta 段是类别说明、不是词条，整段保留。
    """
    if not dict_doc:
        return None
    used = _used_terms(*docs)
    out = {}
    for cat, entries in dict_doc.items():
        if cat == "meta" or not isinstance(entries, dict):
            out[cat] = entries
            continue
        keep = {k: v for k, v in entries.items() if k in used}
        if keep:
            out[cat] = keep
    return out


def _wrap(jin, courtyards, rules_doc, dict_doc=None):
    """instance = data（实例图谱）+ appliedDict / appliedRules（用到的附属知识）。

    两个附属块都是知识中心的**按需子集**：只带解释本实例用得到的部分，无关的不带。
    - appliedRules：只保留 ④ 实际消费的 norms 子树（见 _snapshot_rules）。
    - appliedDict：只保留被用到的词条（见 _extract_dict）。
    类型图谱(appliedType) 已移除——它的信息（每角色 level/material）在 build_instance 阶段
    已落到 data 建筑自带属性上，④ 不再读类型图谱，故 instance 不必再携带它。
    仍为深拷贝，使 instance 自包含、可脱离知识中心独立复现。
    """
    data = {"type": "siheyuan", "jin": jin, "courtyards": courtyards}
    rules_snap = _snapshot_rules(rules_doc)
    inst = {
        "meta": {
            "type": "siheyuan",
            "desc": f"北京{jin}进四合院实例（由类型图谱+规则库合成，工程文件·自包含）",
            "generatedBy": "build_instance (① placeholder)",
            "zeroCoord": True,
        },
        "data": data,
        "appliedRules": rules_snap,
    }
    if dict_doc is not None:
        # 裁剪输入 = 主内容 + 附属 rules 快照（它们引用的词同样算「用到了」）
        inst["appliedDict"] = _extract_dict(dict_doc, data, rules_snap)
    return inst


def _court_namer(rules_doc, dict_doc):
    """院名解析器：返回 court_name(k, jin) -> 中文院名。

    院名唯一事实源 = siheyuan.rules:sequence.naming（图谱驱动）。本层只做「按序求值、首个命中者胜出」，
    不硬编码院名映射；规则里的 name 是命名字典 key，中文名一律由字典 label 给出（字典是命名权威）。
    """
    _naming = (rules_doc.get("sequence") or {}).get("naming") or {}
    _naming_rules = _naming.get("rules") or []
    _naming_fallback = _naming.get("fallback") or {}
    if not _naming_rules or not _naming_fallback:
        raise ValueError("图谱缺陷：siheyuan.rules 缺少 sequence.naming.rules / .fallback")
    CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
              6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}

    def _lbl(key):
        """院名 key -> 字典 label。取不到即报错：缺词条是图谱缺陷，不静默兜底。"""
        for cat in ("院落", "空间角色"):
            v = (dict_doc.get(cat) or {}).get(key)
            if isinstance(v, dict) and isinstance(v.get("label"), str):
                return v["label"]
        raise ValueError("图谱缺陷：院名 key「%s」在命名字典「院落/空间角色」中无 label" % key)

    def court_name(k, jin):
        """第 k 进（共 jin 进）的院名。规则逐条见 siheyuan.rules:sequence.naming（含各条 why）。"""
        for r in _naming_rules:
            at = r.get("at")
            if at == "last":
                if k != jin:
                    continue
            elif at != k:
                continue
            if "jinEq" in r and jin != r["jinEq"]:
                continue
            if "jinGte" in r and jin < r["jinGte"]:
                continue
            return _lbl(r["name"])
        n = k - _naming_fallback.get("ordinalFrom", 2)
        if n < 2:
            # fallback 只服务「同类多次出现」的次院（序数≥2）。落到这里说明规则表有洞：
            # 该进既无规则命中、又不属于次院 —— 是图谱缺陷，报错而不吐「内院·0」这种假名。
            raise ValueError("图谱缺陷：第 %d 进（共 %d 进）在 sequence.naming 中无规则命中，"
                             "且不满足 fallback 序数（序数算出为 %d）" % (k, jin, n))
        return "%s·%s" % (_lbl(_naming_fallback["name"]), CN_NUM.get(n, str(n)))

    return court_name


def _plan_by_jin(jin, norms, type_doc, court_name, rules_doc):
    """① 确定性生成器：按进数合成 courtyards。

    角色与四至**一律取自 rules.occupancy（院落四至默认构成）**——本函数不含任何角色硬编，
    只做「读表 → 查 norms / 类型图谱补数值 → 交给 _finish」。规则改则生成随之改，不可能两处漂移。

    它同时是确定性基线（build_instance）的生成段，供验证与落库使用。

    其他已知点（原散在本函数的注释，现归位）：
      - 游廊暂不生成：抄手游廊是内院环形通道的细部做法，留待「加细节」阶段单独讨论其形制与归属
        （类型图谱 peripheral.youlang 亦标【当前不启用】）。
      - 后门（houmen）是**条件性**构件，不属「每进默认构成」——仅当用户明确提到「宅后临街 / 开后门」
        才在图谱里加，见 siheyuan.rules:position.houmen（用户 2026-09-20 定：默认不设）。
      - 穿堂是正房的一种**做法**（明间南北贯通），随正房归属本院，**不是门**（故图谱记 ring.nan.thru，不记 gate）。
    """
    occ_rules = ((rules_doc.get("occupancy") or {}).get("rules")) or []
    if not occ_rules:
        raise ValueError("图谱缺陷：siheyuan.rules 缺少 occupancy.rules"
                         "（院落四至默认构成 —— 每进哪一侧放什么角色的唯一事实源）")

    def _occupancy_of(k):
        """第 k 进的四至规则：按序求值、首个命中者胜出（与 sequence.naming 同律）。"""
        for r in occ_rules:
            at = r.get("at")
            if at == "middle":
                if not (1 < k < jin):
                    continue
            elif at == "last":
                if k != jin:
                    continue
            elif at != k:
                continue
            if "jinEq" in r and jin != r["jinEq"]:
                continue
            if "jinGte" in r and jin < r["jinGte"]:
                continue
            if "jinLte" in r and jin > r["jinLte"]:
                continue
            return r
        raise ValueError("图谱缺陷：第 %d 进（共 %d 进）在 rules.occupancy 无规则命中" % (k, jin))

    courtyards = []
    for k in range(1, jin + 1):
        rule = _occupancy_of(k)
        sides = rule.get("sides") or {}
        kwargs = {}
        for side in ("bei", "nan", "dong", "xi"):
            spec = sides.get(side)
            if not spec:
                continue              # 该侧无建筑：院墙环自动补独立院墙（yuanqiang）
            room = _room(spec["role"], norms, type_doc)
            for dk in _ROOM_DECL_KEYS:   # gate / chuantang —— 骨架允许的建筑级声明，原样合上
                if dk in spec:
                    room[dk] = spec[dk]
            kwargs[side] = room
        beimen = rule.get("beimen")
        peripheral = rule.get("peripheral") or []
        courtyards.append(_cy(
            k, court_name(k, jin),
            beimen={"role": beimen["role"]} if beimen else None,
            peripheral=[{"role": p["role"]} for p in peripheral] if peripheral else None,
            perimeter=bool(rule.get("perimeter")),
            **kwargs))
    return courtyards


def _finish(jin, courtyards, rules_doc, dict_doc, omit=None):
    """装配收尾：omit 裁剪 -> usage 标注 -> 院角色判定 -> ring 声明 -> 打包附属知识。

    纯机械推导（查表 + 拓扑），零推理。确定性生成器（_plan_by_jin）与 LLM 骨架（assemble_instance）
    共用此段，因此两条路产出的 instance 形状必然一致。
    """
    # 应用 omit：去掉指定侧的建筑（模拟"去掉某厢房"等变体，验证"去掉建筑→外墙自动补上"）。
    # 纯图谱层声明变更，几何层零改动——这正是 boundarySegmentRealization（院墙环分段实现）模型内禀性质。
    omit = set(omit or [])
    for c in courtyards:
        enc = c.get("enclosure", {})
        for side in ("bei", "nan", "dong", "xi"):
            role = _role_of(enc.get(side), None)
            if role and f"{role}_{side}" in omit:
                enc[side] = None

    # 用途(usage)：图谱声明「某角色在某情形下作何用途」——如四进院第二进院正位房作过厅。
    # role 不变、只多一个用途语义（可逆：usage=guoting ⇄「过厅」）。
    # ④ 不自行判断谁是过厅，只按 rules.usage 落字段（图谱驱动）。
    # 必须在 role 标注之前执行——否则主院判定看不到过厅标记，会把「前堂」误当主院。
    for u in (rules_doc.get("usage") or []):
        u_role, u_use, u_at, u_cond = u.get("role"), u.get("usage"), u.get("at"), u.get("when")
        if not u_role or not u_use or not u_at or not _jin_cond_ok(u_cond, jin):
            continue
        if u_at == "erjinyuan_zhengwei":
            target = (courtyards[1].get("enclosure") or {}) if len(courtyards) > 1 else {}
            nm = target.get("bei")
            if nm and nm.get("role") == u_role:
                nm["usage"] = u_use

    # 标注每进角色(waiyuan/neiyuan/houzhaoyuan)，对齐自然语言「外院/内院/后罩院」层级描述
    # neiyuan = 正房所在的主院（后寝）：取最靠南的正房院，但**跳过作过厅的那一进**——
    #       过厅是「前堂」，其正位房虽仍 role=zhengfang，却非后寝主院（前堂后寝，据 rules.usage）。
    # neiyuan 之前=waiyuan（外院/厅房院），之后=houzhaoyuan（后罩院及其前的次院）
    neiyuan_idx = None
    for i, c in enumerate(courtyards):
        enc = c.get("enclosure", {}) or {}
        bei = enc.get("bei") or {}
        if bei.get("role") == "zhengfang" and bei.get("usage") != "guoting":
            neiyuan_idx = i
            break
    for i, c in enumerate(courtyards):
        # 一进院（唯一一进）既是入口院又是主院，无独立院名（就叫「庭院」）→ 角色随院名取
        # tingyuan；多进时正房所在的主院才叫内院 neiyuan（定：一进不叫内院）。
        if neiyuan_idx is None or i == neiyuan_idx:
            c["role"] = "tingyuan" if len(courtyards) == 1 else "neiyuan"
        elif i < neiyuan_idx:
            bei = (c.get("enclosure") or {}).get("bei") or {}
            # 作过厅的那一进是「前堂」(厅房院)，进深介于外院与主院之间，故单列 tingfangyuan
            c["role"] = "tingfangyuan" if bei.get("usage") == "guoting" else "waiyuan"
        else:
            c["role"] = "houzhaoyuan"

    # 图谱层显式声明 ring：每侧墙基底(默认存在) + provider(被谁后檐墙分段实现) + gate（零坐标·语义·可逆）。
    # 几何层只消费此声明，不再自行判断 wallSharing——"先有墙、建筑分段实现替换"由此唯一驱动。
    for i, c in enumerate(courtyards):
        enc = c.get("enclosure", {})
        nr = _role_of(enc.get("bei"), None)
        sr = _role_of(enc.get("nan"), None)
        er = _role_of(enc.get("dong"), None)
        wr = _role_of(enc.get("xi"), None)
        prev_enc = courtyards[i - 1].get("enclosure", {}) if i > 0 else {}
        prev_nr = _role_of(prev_enc.get("bei"), None)
        # bei 侧
        if enc.get("beimen"):
            n_prov, n_kind, n_gate = None, "kaziqiang", "chuihuamen"
        else:
            # bei.gate = 嵌在本院北房上的对外门（后门），与首院 nan.gate=宅门 对称：
            # 它不是独立门屋，而是「把后罩房西北角那间改成门道」，故 provider 仍是该建筑。
            ngate = ((enc.get("bei") or {}).get("gate") or {}).get("role")
            n_prov, n_kind, n_gate = nr, ("houyanqiang" if nr else "weiqiang"), ngate
        # nan 侧：idx0=倒座后檐墙；否则上一进北墙承担（门洞随上一进对齐）
        if i == 0:
            s_prov, s_kind, s_gate, s_thru = sr, ("houyanqiang" if sr else "weiqiang"), (
                "zhaimen" if (enc.get("nan") or {}).get("gate") else None), None
        else:
            s_prov, s_kind = prev_nr, ("houyanqiang" if prev_nr else "weiqiang")
            if prev_enc.get("beimen"):
                s_gate, s_thru = "chuihuamen", None
            elif (prev_enc.get("bei") or {}).get("chuantang"):
                # 穿堂**不是门**：它是上一进北房「明间前后贯通」的做法，属于那座正房、
                # 随正房归属上一进院（有明确归属，不立门实体）。
                # 故 gate=Null，另记 thru：只声明「经何物进入本院」，供联通视图与巡游读取。
                s_gate, s_thru = None, {"via": "chuantang", "of": prev_nr,
                                        "courtyard": courtyards[i - 1].get("name")}
            else:
                s_gate, s_thru = None, None
        c["ring"] = {
            "bei": {"provider": n_prov, "kind": n_kind, "gate": n_gate},
            # nan.gate = 真正的门（宅门/垂花门）；nan.thru = 经上一进正房明间穿堂进入（不是门）。
            "nan": {"provider": s_prov, "kind": s_kind, "gate": s_gate, "thru": s_thru},
            "dong":  {"provider": er, "kind": "houyanqiang" if er else "weiqiang"},
            "xi":  {"provider": wr, "kind": "houyanqiang" if wr else "weiqiang"},
        }

    return _wrap(jin, courtyards, rules_doc, dict_doc)


def _load_knowledge():
    """读知识中心三件套（rules / type / dict）。"""
    return (load_json(os.path.join(KNOWLEDGE_DIR, "siheyuan.rules")),
            load_json(os.path.join(KNOWLEDGE_DIR, "siheyuan.type.json")),
            load_json(os.path.join(KNOWLEDGE_DIR, "dict.json")))


def build_instance(jin, omit=None):
    """① 确定性基线：按进数合成自包含 instance（读知识中心 type+rules）。

    与 LLM 路径共用 _finish 装配段，故两者产出形状一致；omit 用于模拟"去掉某侧建筑"的变体。
    """
    rules_doc, type_doc, dict_doc = _load_knowledge()
    norms = rules_doc.get("norms", {})
    court_name = _court_namer(rules_doc, dict_doc)
    return _finish(jin, _plan_by_jin(jin, norms, type_doc, court_name, rules_doc),
                   rules_doc, dict_doc, omit=omit)


# 骨架里允许出现的「建筑级声明」字段：声明性的（门 / 穿堂）+ 业务量（面阔…）。
# 业务量的**值域**由 rules.paramRanges 约束（校验在 Agent 侧 skill 的装配器 validatePlan 里），
# 本常量只管「可声明」。
_ROOM_DECL_KEYS = ("gate", "chuantang", "miankuo")


def _expand_room(spec, norms, type_doc):
    """骨架里的建筑声明 -> 完整建筑：role 查表补全尺度/等级/材质，声明字段原样合上。

    LLM 只写 role（+ 门/穿堂等声明），尺度数值由本函数从知识中心查表补；
    唯一例外是**业务量**（如 miankuo 面阔）——可由骨架声明，但取值须落在
    rules.paramRanges 声明的值域内（红线只禁坐标/几何量，不禁业务量；§13.4 #1）。
    """
    if not isinstance(spec, dict) or not spec.get("role"):
        raise ValueError("图谱缺陷：骨架中的建筑声明缺 role：%r" % (spec,))
    r = _room(spec["role"], norms, type_doc)
    for k in _ROOM_DECL_KEYS:
        if k in spec:
            r[k] = spec[k]
    return r


def assemble_instance(plan):
    """① LLM 骨架 -> 自包含 instance（装配 = 查表 + 拓扑，零推理）。

    plan 形状（= 实例图谱 data 块的声明式压缩）：
      {"jin": 3,
       "courtyards": [
         {"sequence": 1,
          "enclosure": {"nan": {"role": "daozuofang", "gate": {"role": "zhaimen"}},
                        "beimen": {"role": "chuihuamen"}},
          "peripheral": [{"role": "yingbi"}], "perimeter": true},
         ...]}

    - 尺度数值（面阔/进深/高/台明/等级/材质）由 _expand_room 查知识中心补；
      业务量可在骨架声明（值域受 rules.paramRanges 约束）。
    - 院名不取自骨架，由 sequence.naming 规则推导（命名权归图谱，不归 LLM）。
    - 收尾与 build_instance 共用 _finish，故形状必然一致（零漂移）。
    """
    rules_doc, type_doc, dict_doc = _load_knowledge()
    norms = rules_doc.get("norms", {})
    court_name = _court_namer(rules_doc, dict_doc)

    if not isinstance(plan, dict):
        raise ValueError("图谱缺陷：理解层产物不是对象")
    specs = plan.get("courtyards") or []
    jin = int(plan.get("jin") or len(specs))
    if jin < 1 or len(specs) != jin:
        raise ValueError("图谱缺陷：jin=%s 与 courtyards 数量 %d 不符" % (plan.get("jin"), len(specs)))

    courtyards = []
    for i, spec in enumerate(specs):
        if not isinstance(spec, dict):
            raise ValueError("图谱缺陷：courtyards[%d] 不是对象" % i)
        seq = int(spec.get("sequence") or (i + 1))
        enc_in = spec.get("enclosure") or {}
        enc = {"relation": enc_in.get("relation") or "weihe"}
        for side in ("bei", "nan", "dong", "xi"):
            if isinstance(enc_in.get(side), dict):
                enc[side] = _expand_room(enc_in[side], norms, type_doc)
        # beimen / nanmen 是「门本体」声明（垂花门等），与 _cy 同形：只带 role，不带数值。
        for k in ("beimen", "nanmen"):
            if isinstance(enc_in.get(k), dict):
                enc[k] = {"role": enc_in[k]["role"]}
        c = {"id": "cy%d" % seq, "name": court_name(seq, jin), "sequence": seq,
             "enclosure": enc, "center": {"role": "tingyuan"}}
        if spec.get("perimeter"):
            c["perimeter"] = True
        if spec.get("peripheral"):
            # 与 _cy 一致：附属只记 role（其尺度由 ④ 按 rules.peripheral 取）。
            c["peripheral"] = [{"role": p.get("role")} for p in spec["peripheral"]
                               if isinstance(p, dict)]
        courtyards.append(c)

    return _finish(jin, courtyards, rules_doc, dict_doc)


# ---------------- ④ 几何计算：instance -> 构件列表（连续几何, 绝对坐标, 米, Y-up） ----------------
def _dim(role_obj, key, default):
    return (role_obj or {}).get(key, default)


def _role_of(obj, default):
    if isinstance(obj, dict):
        return obj.get("role", default)
    return default


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

    # 先算每院占地：w 沿 X（面阔），d 沿 Z（进深）
    plotted = []
    for c in courtyards:
        enc = c.get("enclosure", {})
        bei, nan, dong, xi = enc.get("bei"), enc.get("nan"), enc.get("dong"), enc.get("xi")
        ref = bei or nan or {}
        w = _dim(ref, "miankuo", 5) * modus
        nd = _dim(bei, "jinshen", 0) * modus   # 缺房则进深记 0（无幽灵进深）
        sd = _dim(nan, "jinshen", 0) * modus
        cdr = norms.get("courtDepthRatio", 0.6)
        if isinstance(cdr, dict):
            role = c.get("role")
            cdr_map = cdr.get("byRole", {})
            ratio = cdr_map.get(role, cdr.get("default", 0.6)) if role in cdr_map else cdr.get("default", 0.6)
        else:
            ratio = cdr
        court_depth = w * ratio   # 露天院落进深=面阔×按角色比例(waiyuan浅/neiyuan大/houzhaoyuan中)
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
            "骨架请先经装配器（assemble.mjs / assemble_instance）补全数值再调用" % fn)
    return data


def compute_geometry(instance):
    """④ 几何计算：instance -> 构件列表。每个构件 = {role, center:{x,y,z}, size:{w,h,d}}。

    - 只读 instance（data + appliedRules），不硬编码任何规制数字。
    - 输出是构件（连续几何），不是 box、不是空间。庭院虚空不输出。
    - 算不出任何构件即报图谱缺陷 —— **绝不静默返回 []**（见 _graph_data 的 why）。
    """
    _graph_data(instance, "compute_geometry")
    plotted, norms, modus = _layout(instance)
    geometry = []
    for idx, p in enumerate(plotted):
        zc = p["zc"]
        w, d = p["w"], p["d"]
        nd, sd = p["nd"], p["sd"]

        if p["bei"]:
            nrole = p["bei"]
            ngate = ((nrole or {}).get("gate") or {}).get("role")
            if ngate:
                # 对外门嵌在北房里（后门 = 西北角一间改门道）→ 拆「东段普通房 + 西端贯通门道」
                geometry.extend(_geo_back_gate(0, w, nd, zc + d / 2 - nd / 2, nrole, ngate, norms))
            elif (nrole or {}).get("chuantang"):
                geometry.extend(_geo_zhengfang_chuantang(0, w, nd, zc + d / 2 - nd / 2, nrole, norms))
            else:
                # 北侧房屋朝南开口（庭院在南）——开口朝向由房屋所在侧决定，不靠角色名硬判
                geometry.extend(_geo_wing(0, w, nd, zc + d / 2 - nd / 2, nrole, "S", norms))
        if p["nan"]:
            has_gate = bool((p["nan"] or {}).get("gate"))
            geometry.extend(_geo_daozuo(0, w, sd, zc - d / 2 + sd / 2, p["nan"], norms, has_gate))
        # 东西厢：长边沿 Z（面阔），厚沿 X（进深）。
        # Z 向填充「正房南檐 -> 倒座北檐」空隙，中心 = zc + (sd-nd)/2，
        # 使其与正房只在角上相接、体积不重叠（修此前 厢房/正房 空间重叠）。
        ew_z = zc + (sd - nd) / 2
        if p["dong"]:
            ed = _dim(p["dong"], "jinshen", 0) * modus
            el = _xiangfang_length(p["dong"], norms, d, nd, sd, modus)
            geometry.extend(_geo_dongxi(+(w / 2 - ed / 2), el, ed, ew_z, p["dong"], norms))
        if p["xi"]:
            ed = _dim(p["xi"], "jinshen", 0) * modus
            el = _xiangfang_length(p["xi"], norms, d, nd, sd, modus)
            geometry.extend(_geo_dongxi(-(w / 2 - ed / 2), el, ed, ew_z, p["xi"], norms))

        # 垂花门（仅一进→二进卡子墙正中、中轴线）：beimen 表示与前一院落的边界，门道南北贯通
        enc = p["c"].get("enclosure", {})
        if enc.get("beimen"):
            gz = zc + d / 2                         # 嵌在卡子墙缺口处(本院北墙)
            geometry.extend(_geo_chuihua(gz, w, _role_of(enc["beimen"], "chuihuamen"), norms))
        if enc.get("nanmen"):
            gz = zc - d / 2
            geometry.extend(_geo_chuihua(gz, w, _role_of(enc["nanmen"], "chuihuamen"), norms))

        # 围合构件（实体）：游廊 / 影壁
        # 注：游廊分支当前**不启用** —— 各进 peripheral 已不再声明 youlang（留待加细节阶段讨论形制与归属）。
        #     分支与其实现 _geo_youlang 一并保留，便于届时直接恢复，不要当成死代码删掉。
        for per in (p["c"].get("peripheral") or []):
            if not isinstance(per, dict):
                continue
            prole = per.get("role")
            if prole == "youlang":
                geometry.extend(_geo_youlang(w, nd, zc, d, norms))
            elif prole == "yingbi":
                geometry.append(_geo_yingbi(w, sd, zc, d, norms))

        # 院墙环（boundarySegmentRealization）：先画完整一圈墙、门(gate)开缺；
        # 贴边建筑（后檐墙/山墙）的实现不在此预判——统一交给末尾 _resolve_boundary 去重。
        if p["c"].get("perimeter"):
            geometry.extend(_geo_wall_ring(p["c"], w, zc, d, norms, draw_south=(idx == 0)))

    # 边界去重：同一条墙线上建筑墙优先于独立院墙(yuanqiang)，被覆盖的院墙段按区间相减掉。
    resolved = _resolve_boundary(geometry, norms)
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

    # 宅门在东南角、不在中轴：门道中心 x 直接取实际构件里 zhaimen 的中心（避免公式两处实现漂移）
    gxs = [g.get("center", {}).get("x", 0.0)
           for g in (comps or []) if g.get("role") == "zhaimen"]
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
            nlabel = _label_of((p["bei"] or {}).get("role"), "院北")
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
            hall = _label_of(nm.get("usage"), "过厅")
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


def _geo_room(role, cx, cz, W, H, D, open_side=None, norms=None, spec=None):
    """房间 = 台基(或地面) + 屋顶 + 四壁（朝庭院一侧留门洞，而非整面掏空），内部空心。

    ④ 本职：把房间拆成可独立体素化的子构件，而非塞一整个实心长方体。
    open_side ∈ {'N','S','E','W'} 或其列表：该侧（们）朝庭院，墙面居中留门洞。
    传列表（如 ['S','N']）可表达「贯通门道」：南北双向开口。
    墙/顶厚度 t 取自 norms.room.thickness（原代码常量 WALL_THICKNESS）。

    底部构件：若 norms.<role>.taiming 已声明（＝图谱声明该角色有台基，对照类型图谱
    structs 是否含 taiji），则生成为「台基」构件——台明高取其值、自墙面线外扩
    norms.room.taimingOutset；未声明则回落为原「地面」。
    （原「地面」是 dict.构件 里没有的构件名，改判为 taiji 后台基与图谱构件表自洽。）
    """
    t = float(_norms_get(norms, ("room", "thickness"), "房间墙/顶/地厚"))
    tm = _spec_get(spec, norms, role, "taiming")
    if tm:
        tm = float(tm)
        outset = float(_norms_get(norms, ("room", "taimingOutset"), "台基外扩"))
        base = _geo_slab("taiji", cx, tm / 2, cz, W + 2 * outset, tm, D + 2 * outset)
    else:
        tm = t
        base = _geo_slab(role, cx, t / 2, cz, W, t, D)      # 无台基角色：回落为地面
    floor_top = tm
    roof_bot = H - t
    wall_h = roof_bot - floor_top                       # 墙高（地面顶 -> 屋顶底）
    y_wall = (floor_top + roof_bot) / 2                 # 墙竖向中点（floor_top=t 时即 H/2）
    open_set = {open_side} if isinstance(open_side, str) else set(open_side or [])
    comps = [
        base,
        _geo_slab(role, cx, H - t / 2, cz, W, t, D),        # 屋顶
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
    return comps


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


def _geo_wing(cx, w, depth, zc, role_obj, open_side, norms):
    """南北向屋翼（正房/倒座/后罩）：长边沿 X（面阔），厚沿 Z（进深）。

    房间=围合结构，朝庭院一侧留敞口。open_side 由调用方按房屋在院子里的位置给定
    （位于北侧者朝南开口、南侧者朝北）——这是几何事实，不再靠角色名硬判。
    高度取自该栋建筑自带 height（回落 norms.<role>.height；原代码常量 WING_HEIGHT）。
    """
    role = role_obj.get("role")
    return _geo_room(role, cx, zc, w, _role_height(norms, role, role_obj), depth, open_side, norms, role_obj)


def _geo_daozuo(cx, w, sd, zc, role_obj, norms, has_gate):
    """倒座房：最外院(含宅门)拆为「西段普通倒座房 + 东端大门间(门道+门楼)」；
    非最外院则整排普通倒座房。④ 本职：围合结构算清，⑤ 不过问空心。

    - 西段：普通倒座房，朝北('N')留门洞，居中偏西。
    - 东端大门间：门道(朝东'E'留大门洞)+ 抬高门楼(屋顶高于普通房)，位于院落东南角。
    """
    if not has_gate:
        return _geo_wing(cx, w, sd, zc, role_obj, "N", norms)
    role = role_obj.get("role")
    room_h = _role_height(norms, role, role_obj)          # 门道高 = 同排普通房高
    gs = round(float(_norms_get(norms, ("zhaimen", "gateSpan"), "大门门道面阔")), 3)
    gh = round(float(_norms_get(norms, ("zhaimen", "height"), "大门门楼高")), 3)
    margin = float(_norms_get(norms, ("zhaimen", "eastMargin"), "大门东侧与院墙留白"))
    gs = round(min(gs, w - 0.6), 3)                       # 大门段不超倒座房总面阔
    gate_center = round(cx + (w / 2 - gs / 2 - margin), 3)  # 东南角留白
    seg_right = gate_center - gs / 2                      # 西段右边界（=门左缘）
    x_main = round((-w / 2 + seg_right) / 2, 3)
    w_main = round(seg_right + w / 2, 3)
    comps = []
    # 西段普通倒座房（朝北留门洞，与内院相对）
    comps.extend(_geo_room(role, x_main, zc, w_main, room_h, sd, "N", norms, role_obj))
    # 东端大门：门道（南=街门、北=内院，双向贯通）+ 门楼（屋顶抬高）
    comps.extend(_geo_room("zhaimen", gate_center, zc, gs, room_h, sd, ["S", "N"], norms))
    comps.extend(_geo_gate_tower("zhaimen", gate_center, zc, gs, room_h, gh, sd, norms))
    return comps


def _geo_back_gate(cx, w, depth, zc, role_obj, gate_role, norms):
    """末进北房（后罩房）带后门：拆为「东段普通后罩房 + 西端后门间(南北贯通)」。

    与 _geo_daozuo（倒座房带宅门）同法、东西对称，两点差异：
      · 门在西端（西北角）而非东端——见 rules.position.houmen：后门开在院落西北角。
      · 不带门楼：后门是「一间改门道」的随墙小门，门道高 = 同排后罩房高（不单列 height）。
    门洞的开缺在 _geo_wall_ring 的 ns_wall(gate="houmen") 分支里同步做——否则墙环会把
    这段贯通门道堵死（门道北面本就是敞口，没有建筑墙可供 _resolve_boundary 替换）。
    """
    role = role_obj.get("role")
    room_h = _role_height(norms, role, role_obj)          # 门道高 = 同排普通房高
    gs = round(float(_norms_get(norms, ("houmen", "gateSpan"), "后门门道面阔")), 3)
    margin = float(_norms_get(norms, ("houmen", "westMargin"), "后门西侧与院墙留白"))
    gs = round(min(gs, w - 0.6), 3)                       # 后门段不超后罩房总面阔
    gate_center = round(cx - (w / 2 - gs / 2 - margin), 3)  # 西北角留白
    seg_left = gate_center + gs / 2                      # 东段左边界（=门右缘）
    x_main = round((seg_left + w / 2) / 2, 3)
    w_main = round(w / 2 - seg_left, 3)
    comps = []
    comps.extend(_geo_room(role, x_main, zc, w_main, room_h, depth, "S", norms, role_obj))
    comps.extend(_geo_room(gate_role, gate_center, zc, gs, room_h, depth, ["S", "N"], norms))
    return comps


def _geo_dongxi(cx, el, ed, zc, role_obj, norms):
    """东西厢：长边沿 Z（面阔），厚沿 X（进深）。
    房间=围合结构，朝庭院中心留敞口：东厢朝西('W')，西厢朝东('E')。
    高度取自该栋建筑自带 height（回落 norms.<role>.height；原代码常量 WING_HEIGHT）。"""
    role = role_obj.get("role")
    open_side = "W" if cx > 0 else "E"
    return _geo_room(role, cx, zc, ed, _role_height(norms, role, role_obj), el, open_side, norms, role_obj)


def _xiangfang_length(role_obj, norms, d, nd, sd, modus):
    """④ 厢房沿庭院方向(Z)长度：读 rules.layout.xiangfang 约束，不再硬编码填满庭院。

    - lengthMode=miankuo：长度取自身面阔(间数×modus)，而非 d-nd-sd
    - aisle：南北与正房/倒座各留通道，使中央庭院完整保留
    - zAlign=center 由调用方 ew_z 实现（ew_z 已是庭院净深中心）
    """
    layout = _norms_get(norms, ("layout", "xiangfang"), "厢房布局约束（lengthMode/aisle/zAlign）")
    aisle = float(layout.get("aisle", 0))
    own = float(_dim(role_obj, "miankuo", 0)) * modus  # 自身面阔(间数×modus)
    court_net = d - nd - sd                          # 庭院净深
    return round(min(own, court_net - 2 * aisle), 3)


def _geo_zhengfang_chuantang(cx, w, depth, zc, role_obj, norms):
    """正房明间(中央开间)为穿堂：南北双向开门，连通内院与后院；左右次间为普通房间(仅朝南开敞)。

    ④ 本职：把正房拆成 3 个开间子构件 —— 左右次间(朝南留门洞) + 中央明间(南北贯通门道)。
    门道方向由 KB 的 chuantang 标记驱动（即正房明间过厅），⑤ 实心体素化即可。
    """
    role = role_obj.get("role", "zhengfang")
    H = _role_height(norms, role, role_obj)
    miankuo = _dim(role_obj, "miankuo", 5)
    bay = (w / miankuo) if miankuo else w            # 每间面阔(米)
    central = min(bay, w * 0.4)                       # 中央明间(约 1 间)，作穿堂
    side = (w - central) / 2
    comps = []
    if side > 0.2:
        comps.extend(_geo_room(role, cx - (central / 2 + side / 2), zc, side, H, depth, "S", norms, role_obj))
        comps.extend(_geo_room(role, cx + (central / 2 + side / 2), zc, side, H, depth, "S", norms, role_obj))
    # 中央明间 = 穿堂（南北贯通）
    comps.extend(_geo_room(role, cx, zc, central, H, depth, ["S", "N"], norms, role_obj))
    return comps


def _geo_chuihua(zc, w, role, norms):
    """垂花门(二门)：卡子墙正中、中轴线，门道南北贯通(门洞)，门楼略抬高。

    ④ 本职：门道为围合结构(南北开门)，门楼独立子构件；⑤ 实心体素化即可。
    不再用实心方块占位（此前错误）。
    门道面阔 gs 取自 norms.chuihuamen.gateSpan，与 _geo_wall_ring 开洞同源，
    保证「门体宽 == 卡子墙洞口宽」，两侧不留通缝。
    """
    gs = round(float(_norms_get(norms, ("chuihuamen", "gateSpan"), "垂花门面阔")), 3)
    gh = round(float(_norms_get(norms, ("chuihuamen", "height"), "垂花门楼高")), 3)
    depth = float(_norms_get(norms, ("chuihuamen", "depth"), "垂花门道进深"))
    base_h = float(_norms_get(norms, ("room", "heightDefault"), "门道基准高"))
    comps = _geo_room(role, 0, zc, gs, base_h, depth, ["S", "N"], norms)   # 门道南北贯通
    if gh > base_h + 0.05:
        comps.extend(_geo_gate_tower(role, 0, zc, gs, base_h, gh, depth, norms))   # 门楼略高
    return comps


def _geo_youlang(w, nd, zc, d, norms):
    """游廊：正房前檐的柱廊——柱列 + 廊顶，通透无实墙（抄手游廊的直段）。

    【当前不启用】各进 peripheral 未声明 youlang，故本函数暂不产生体素；
    留待「加细节」阶段确定抄手游廊的形制与归属后恢复。保留实现，勿删。

    廊与院墙不同：不围合，只提供有顶通道。中轴穿堂口按 norms.door.width 断开，
    让出正房明间南北通行的门道（否则就成了堵在正房前的一堵墙）。
    尺寸全部取自 norms.peripheral.youlang（原为代码内联魔法数字）。
    """
    cfg = _norms_get(norms, ("peripheral", "youlang"), "游廊尺寸")
    H = float(cfg["height"])
    depth = float(cfg["depth"])
    span_ratio = float(cfg["spanRatio"])
    col_spacing = float(cfg["colSpacing"])
    top_h = float(cfg["roofThickness"])
    col = float(_norms_get(norms, ("room", "thickness"), "游廊柱截面"))
    gap = float(_norms_get(norms, ("door", "width"), "穿堂口宽"))
    out = []
    zpos = zc + d / 2 - nd - depth / 2
    half = (w * span_ratio) / 2.0
    for a, b in ((-half, -gap / 2.0), (gap / 2.0, half)):    # 左右两段，中间让开穿堂
        seg = b - a
        if seg <= 0.05:
            continue
        # 廊顶：薄板，跨该段
        out.append(_geo_slab("youlang", (a + b) / 2.0, H - top_h / 2.0, zpos, seg, top_h, depth))
        # 柱列：两端 + 按 colSpacing 均布
        n = max(2, int(round(seg / col_spacing)) + 1)
        for i in range(n):
            x = a + seg * i / (n - 1)
            out.append(_geo_slab("youlang", x, (H - top_h) / 2.0, zpos, col, H - top_h, col))
    return out


def _geo_yingbi(w, sd, zc, d, norms):
    """影壁：入口处的屏墙。尺寸取自 norms.peripheral.yingbi（原为代码内联魔法数字）。"""
    cfg = _norms_get(norms, ("peripheral", "yingbi"), "影壁尺寸")
    bw, H, thick = float(cfg["width"]), float(cfg["height"]), float(cfg["depth"])
    zpos = zc - d / 2 + sd + float(cfg["zOffset"])
    return {"role": "yingbi",
            "center": {"x": round(w / 2 - bw / 2 - float(cfg["xInset"]), 3),
                       "y": H / 2, "z": round(zpos, 3)},
            "size": {"w": bw, "h": H, "d": thick}}


def _geo_wall(cx, cz, width_x, H, depth_z, role):
    """单段墙：宽沿 X(width_x)，厚沿 Z(depth_z)。"""
    return {"role": role,
            "center": {"x": round(cx, 3), "y": H / 2, "z": round(cz, 3)},
            "size": {"w": round(width_x, 3), "h": H, "d": round(depth_z, 3)}}


def _geo_wall_ring(c, w, zc, d, norms, draw_south=True):
    """院墙环：先实例化「完整一圈墙」，不预判任何建筑位置（boundarySegmentRealization）。
    - 北/南按 gate 开缺（zhaimen 东南角 / chuihuamen 中段 / houmen 西北角）。穿堂不在此开缺（它不是门）。
    - 东西墙先画整段；贴边建筑（后檐墙/山墙）的占位由 _resolve_boundary 统一去重。
    - 每进只承担自己的北界；整院南外墙仅由最南一进(idx0)承担。
    - 图谱 ring 保留 provider 语义声明（可逆），几何实现不再消费它做预判。
    """
    ring = c.get("ring", {}) or {}
    H = float(_norms_get(norms, ("wall", "height"), "院墙高"))
    T = float(_norms_get(norms, ("wall", "thickness"), "院墙厚"))
    t = float(_norms_get(norms, ("room", "thickness"), "墙面线偏移基准（取房间墙厚）"))
    half = w / 2 - t / 2                     # 东西墙中心 X（与厢房外墙同一墙面线）
    zN = zc + d / 2 - t / 2                 # 北墙与正房/后罩房后檐墙共线
    zS = zc - d / 2 + t / 2                 # 南墙与倒座后檐墙共线
    out = []

    def ns_wall(zc_wall, gate):
        if gate == "zhaimen":
            gs = float(_norms_get(norms, ("zhaimen", "gateSpan"), "大门门道面阔"))
            gx = round(w / 2 - gs / 2 - float(_norms_get(norms, ("zhaimen", "eastMargin"), "大门东侧留白")), 3)
            gh = gs / 2
            l_seg = (gx - gh) - (-half)
            if l_seg > 0.01:
                out.append(_geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (gx + gh)
            if r_seg > 0.01:
                out.append(_geo_wall((gx + gh) + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        elif gate == "chuihuamen":
            # 垂花门门洞宽 = 门体面阔(gateSpan)，与宅门同法从 norms 取。
            # 穿堂不在此开缺：它的门洞由 _geo_zhengfang_chuantang 在正房明间上生成
            # （正房被拆为「左右次间 + 中央明间南北贯通」）；且本函数仅在首院画南墙(draw_south)，
            # 非首院的南界由上一进北房后檐墙承担，本就轮不到墙环开缺。
            gs = float(_norms_get(norms, ("chuihuamen", "gateSpan"), "垂花门面阔"))
            gh = gs / 2
            l_seg = (0 - gh) - (-half)
            if l_seg > 0.01:
                out.append(_geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (0 + gh)
            if r_seg > 0.01:
                out.append(_geo_wall(gh + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        elif gate == "houmen":
            # 后门：门洞开在**西端**（西北角），与宅门的东南角相对。此处必须开缺——
            # 后门间北面本就是敞口（南北贯通），没有建筑墙可供 _resolve_boundary 替换，
            # 若墙环照整段画，门道会被外围围墙堵死。
            gs = float(_norms_get(norms, ("houmen", "gateSpan"), "后门门道面阔"))
            gx = round(-(w / 2 - gs / 2 - float(_norms_get(norms, ("houmen", "westMargin"),
                                                          "后门西侧留白"))), 3)
            gh = gs / 2
            l_seg = (gx - gh) - (-half)
            if l_seg > 0.01:
                out.append(_geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (gx + gh)
            if r_seg > 0.01:
                out.append(_geo_wall((gx + gh) + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        else:
            out.append(_geo_wall(0, zc_wall, w, H, T, "yuanqiang"))

    # 北墙：本进与后一进的分界（最北一进的北墙 = 整院北外墙）
    ns_wall(zN, (ring.get("bei") or {}).get("gate"))
    # 南墙：仅最南一进(idx0)画 —— 即整院南外墙；其余进的南界由前一进北墙承担
    if draw_south:
        ns_wall(zS, (ring.get("nan") or {}).get("gate"))
    # 东西墙：先画整段；贴边建筑的占位由 _resolve_boundary 统一去重
    out.append(_geo_wall(half, zc, T, H, d - t, "yuanqiang"))
    out.append(_geo_wall(-half, zc, T, H, d - t, "yuanqiang"))
    return out


def _resolve_boundary(components, norms):
    """边界墙去重（boundarySegmentRealization 的几何实现）。

    同一条共线墙线上，建筑墙(后檐墙/山墙, pri=1)优先于独立院墙(yuanqiang, pri=0)：
    把被建筑覆盖的区间从 yuanqiang 段中【区间相减】掉（非整段删），保留真正空档。

    建筑自身的门/窗洞口（由矮薄的门楣标记，见 _geo_front_wall）一并算作「建筑覆盖段」——
    洞口是建筑的开口，独立院墙不得残留在洞口中（否则会把穿堂/门洞堵死）。
    resolver 只看真实几何覆盖，不预判任何建筑位置——增删建筑时该侧院墙自动补/让。
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
            if g.get("role") != "yuanqiang":
                holes_extra.append([orient, line, lo, hi])
            continue
        pri = 0 if g.get("role") == "yuanqiang" else 1
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
def _voxelize_component(g, vox, labels):
    """构件(连续几何) -> 体素 BOX 网格（构件 : box = 图像 : 像素）。

    纯几何转换：把传入的构件实心切成边长为 vox 的体素网格。构件本身是实心还是
    空心围合（如房间拆成的墙/顶/地子构件），由 ④ 几何计算引擎决定，⑤ 不过问。
    label 取自命名字典（labels 表由调用方一次取好，逐构件复用）；
    color 由所属构件继承（点选任意体素都能识别其构件）。
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
    label = _label_of(role, table=labels)
    color = ROLE_COLORS.get(role, 0x999999)
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


def geometry_to_boxes(geometry, vox=VOXEL_SIZE):
    """⑤ 几何造型引擎：构件 -> 体素 BOX 清单（真实多体素化，非 1 构件=1 box 占位）。

    选定 BOX 作为 MVP 表现基元，把每个构件按 VOXEL_SIZE 体素化成 box 网格。
    label 取自命名字典（此处一次取表、逐构件复用），color 由所属构件继承。
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
    labels = _dict_labels()
    boxes = []
    for g in geometry:
        boxes.extend(_voxelize_component(g, vox, labels))
    if not boxes:
        raise ValueError(
            "图谱缺陷：构件清单非空却算不出任何体素 —— 构件缺 center/size（零尺寸构件"
            "不产生体素），通常说明该清单不是 compute_geometry 的产出")
    return boxes


# ---------------- 串联入口（app.py 仅调此函数） ----------------
def instance_to_boxes(instance):
    """instance -> 体素 BOX 清单（① -> ④ -> ⑤）。"""
    return geometry_to_boxes(compute_geometry(instance))


# ---------------- 工具：读取/种子 ----------------
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_seed():
    return load_json(os.path.join(DATA_DIR, "siheyuan.instance.json"))
