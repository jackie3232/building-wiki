"""
④ 几何计算引擎 + ⑤ 几何造型引擎(BOX 出口) + ① 合成占位
------------------------------------------------
输入 ：实例图谱工程文件（server/data/instances/*.json）
       自包含：data 块为实例数据（拓扑+尺度具体值），appliedRules 为规则快照。
       ④ 只读 instance 整体（data + appliedRules），不碰外部 dict.json / rules.json。
       ①（text_to_instance / build_instance）读知识中心（type.json + rules.json）合成 instance，
       属 ① 本职；④ 不读外部知识文件。
输出 ：⑤ 体素 BOX 清单（场景坐标：Y-up，单位米）
       每个 box = {x,y,z, w,h,d, role, label, color}

分层（见 几何计算引擎IO契约.md）：
- build_instance(jin)        = ① 占位：读 type+rules，按进数合成自包含 instance
- text_to_instance(text)     = ① 占位：解析 NL 进数 -> build_instance
- compute_geometry(instance) = ④：instance -> 构件列表（连续几何，绝对坐标，无 color/label）
- geometry_to_boxes(geo)     = ⑤：构件 -> box 像素网格（选 Box 基元 + 补 label/color）
- instance_to_boxes(inst)    = 串联 ①->④->⑤（app.py 仅调此）
- build_tour_path(inst, geo) = ④ 布局 + 实际构件 -> 游览路线 DATA（纯展示层派生，实时生成，不回灌 ④/⑤）

设计铁律（见 架构设计总览.md §7/§9/§14、几何计算引擎IO契约.md）：
- 零坐标：instance 不含 x/y/z；④ 据「间」模数与拓扑算绝对坐标（④ 本职）。
- ④ 只吃 instance（data + appliedRules + appliedType），模数/尺度等换算标准全部从图谱取，无一硬编码。
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

# role key -> 兜底中文名 / 颜色（⑤ 造型层使用，纯内置，不依赖外部词表）
ROLE_LABELS = {
    "zhengfang": "正房", "xiangfang": "厢房", "daozuofang": "倒座房",
    "houzhaofang": "后罩房", "chuihuamen": "垂花门", "erfang": "耳房",
    "youlang": "游廊", "yingbi": "影壁", "tingyuan": "庭院", "yuanqiang": "院墙",
    "zhaimen": "大门", "taiji": "台基",
}
# 用途 key -> 中文名（仅展示层回落用，与 ROLE_LABELS 同类：图谱未带 label 时的兜底）
USAGE_LABELS = {
    "guoting": "过厅",
}
ROLE_COLORS = {
    "zhengfang": 0xC0504D, "xiangfang": 0xE0A030, "daozuofang": 0x4F81BD,
    "houzhaofang": 0x9B59B6, "chuihuamen": 0x82A33A, "erfang": 0x9B59B6,
    "youlang": 0x808080, "yingbi": 0xB0A040, "tingyuan": 0xCFCFCF, "yuanqiang": 0x7F7F7F,
    "zhaimen": 0x8B4513, "taiji": 0x9E9284,
}

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


# ---------------- ① 合成占位：NL -> 自包含 instance ----------------
def _parse_jin(text):
    """从 NL 文本解析进数；未识别默认 3。"""
    if not text:
        return 3
    m = re.search(r'([一二三四五六七八九十\d])\s*进', text)
    if not m:
        return 3
    tok = m.group(1)
    if tok.isdigit():
        return max(1, min(int(tok), 10))
    return _CN_NUM.get(tok, 3)


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
         "jinshen": n.get("jinshen", 3)}
    for k in ("height", "taiming"):
        if n.get(k) is not None:
            r[k] = n[k]
    for k in ("level", "material"):
        if t.get(k) is not None:
            r[k] = t[k]
    return r


def _south_with_gate(norms, type_doc=None):
    """最外院(sequence==1)倒座房：附大门(zhaimen)，使 ④ 渲染东南角宅门。"""
    r = _room("daozuofang", norms, type_doc)
    r["gate"] = {"role": "zhaimen"}
    return r


def _cy(seq, name, north=None, south=None, east=None, west=None,
        northGate=None, southGate=None, peripheral=None, perimeter=False):
    enc = {"relation": "weihe"}
    if north: enc["north"] = north
    if south: enc["south"] = south
    if east: enc["east"] = east
    if west: enc["west"] = west
    if northGate: enc["northGate"] = northGate
    if southGate: enc["southGate"] = southGate
    c = {"id": f"cy{seq}", "name": name, "sequence": seq,
         "enclosure": enc, "center": {"role": "tingyuan"}}
    if perimeter:
        c["perimeter"] = True
    if peripheral:
        c["peripheral"] = peripheral
    return c


def _snapshot_rules(rules_doc):
    """规则库 -> appliedRules 快照（深拷贝，保证 instance 自包含、可独立复现）。

    ④ 不再为任何规制数字提供代码兜底，故此处也不补齐缺字段——缺了回知识中心补。
    """
    snap = json.loads(json.dumps(rules_doc))
    if not isinstance(snap.get("norms"), dict) or "modus" not in snap["norms"]:
        raise ValueError("图谱缺陷：siheyuan.rules 缺少 norms.modus")
    return snap


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


def _wrap(jin, courtyards, rules_doc, type_doc=None, dict_doc=None):
    """instance = data（实例图谱）+ appliedDict / appliedRules / appliedType（用到的附属知识）。

    三个附属块都是知识中心的**按需子集**：只带解释本实例用得到的部分，无关的不带。
    仍为深拷贝，使 instance 自包含、可脱离知识中心独立复现。
    """
    data = {"type": "siheyuan", "jin": jin, "courtyards": courtyards}
    rules_snap = _snapshot_rules(rules_doc)
    type_snap = json.loads(json.dumps(type_doc)) if type_doc is not None else None
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
    if type_snap is not None:
        inst["appliedType"] = type_snap
    if dict_doc is not None:
        # 裁剪输入 = 主内容 + 两个附属快照（它们引用的词同样算「用到了」）
        inst["appliedDict"] = _extract_dict(dict_doc, data, type_snap, rules_snap)
    return inst


def build_instance(jin, omit=None):
    """① 占位：按进数合成自包含 instance（读知识中心 type+rules）。"""
    rules_doc = load_json(os.path.join(KNOWLEDGE_DIR, "siheyuan.rules"))
    type_doc = load_json(os.path.join(KNOWLEDGE_DIR, "siheyuan.type.json"))
    dict_doc = load_json(os.path.join(KNOWLEDGE_DIR, "dict.json"))
    norms = rules_doc.get("norms", {})
    courtyards = []

    if jin <= 1:
        courtyards.append(_cy(1, "正院",
            north=_room("zhengfang", norms, type_doc), south=_south_with_gate(norms, type_doc),
            east=_room("xiangfang", norms, type_doc), west=_room("xiangfang", norms, type_doc),
            peripheral=[{"role": "youlang"}, {"role": "yingbi"}], perimeter=True))
    elif jin == 2:
        courtyards.append(_cy(1, "外院", south=_south_with_gate(norms, type_doc),
                              northGate={"role": "chuihuamen"}, perimeter=True))
        courtyards.append(_cy(2, "内院", north=_room("zhengfang", norms, type_doc),
            east=_room("xiangfang", norms, type_doc), west=_room("xiangfang", norms, type_doc),
            peripheral=[{"role": "youlang"}, {"role": "yingbi"}], perimeter=True))
    else:
        # jin >= 3：仅一进→二进设垂花门；内院正房明间为穿堂(南北贯通)，连通下一进；
        #           末进为后院(后罩房)，经穿堂/夹道连通，不设独立门楼。
        courtyards.append(_cy(1, "外院", south=_south_with_gate(norms, type_doc),
                              northGate={"role": "chuihuamen"}, perimeter=True))
        for k in range(2, jin):
            # 内院：正房明间(中央开间)为穿堂，南北开门连通后院；其余院落边界不设垂花门
            zf = _room("zhengfang", norms, type_doc)
            zf["chuantang"] = True
            peripheral = [{"role": "youlang"}, {"role": "yingbi"}] if k == 2 else None
            courtyards.append(_cy(k, f"内院{k-1}",
                north=zf, east=_room("xiangfang", norms, type_doc),
                west=_room("xiangfang", norms, type_doc), peripheral=peripheral, perimeter=True))
        courtyards.append(_cy(jin, "后院",
            north=_room("houzhaofang", norms, type_doc), east=_room("xiangfang", norms, type_doc),
            west=_room("xiangfang", norms, type_doc), perimeter=True))

    # 应用 omit：去掉指定侧的建筑（模拟"去掉某厢房"等变体，验证"去掉建筑→外墙自动补上"）。
    # 纯图谱层声明变更，几何层零改动——这正是 boundarySegmentRealization（院墙环分段实现）模型内禀性质。
    omit = set(omit or [])
    for c in courtyards:
        enc = c.get("enclosure", {})
        for side in ("north", "south", "east", "west"):
            role = _role_of(enc.get(side), None)
            if role and f"{role}_{side}" in omit:
                enc[side] = None

    # 标注每进角色(front/main/back)，对齐自然语言「前院/主院/后院」层级描述
    # main = 最靠南(序列最小)的正房院；main 之前=front(前院)，之后=back(后院)
    main_idx = None
    for i, c in enumerate(courtyards):
        enc = c.get("enclosure", {}) or {}
        north = enc.get("north") or {}
        if north.get("role") == "zhengfang":
            main_idx = i
            break
    for i, c in enumerate(courtyards):
        if main_idx is None:
            c["role"] = "main"
        elif i < main_idx:
            c["role"] = "front"
        elif i == main_idx:
            c["role"] = "main"
        else:
            c["role"] = "back"

    # 图谱层显式声明 ring：每侧墙基底(默认存在) + provider(被谁后檐墙分段实现) + gate（零坐标·语义·可逆）。
    # 几何层只消费此声明，不再自行判断 wallSharing——"先有墙、建筑分段实现替换"由此唯一驱动。
    for i, c in enumerate(courtyards):
        enc = c.get("enclosure", {})
        nr = _role_of(enc.get("north"), None)
        sr = _role_of(enc.get("south"), None)
        er = _role_of(enc.get("east"), None)
        wr = _role_of(enc.get("west"), None)
        prev_enc = courtyards[i - 1].get("enclosure", {}) if i > 0 else {}
        prev_nr = _role_of(prev_enc.get("north"), None)
        # north 侧
        if enc.get("northGate"):
            n_prov, n_kind, n_gate = None, "kaziqiang", "chuihuamen"
        else:
            n_prov, n_kind, n_gate = nr, ("houyanqiang" if nr else "weiqiang"), None
        # south 侧：idx0=倒座后檐墙；否则上一进北墙承担（门洞随上一进对齐）
        if i == 0:
            s_prov, s_kind, s_gate = sr, ("houyanqiang" if sr else "weiqiang"), (
                "zhaimen" if (enc.get("south") or {}).get("gate") else None)
        else:
            s_prov, s_kind = prev_nr, ("houyanqiang" if prev_nr else "weiqiang")
            if prev_enc.get("northGate"):
                s_gate = "chuihuamen"
            elif (prev_enc.get("north") or {}).get("chuantang"):
                s_gate = "chuantang"
            else:
                s_gate = None
        c["ring"] = {
            "north": {"provider": n_prov, "kind": n_kind, "gate": n_gate},
            "south": {"provider": s_prov, "kind": s_kind, "gate": s_gate},
            "east":  {"provider": er, "kind": "houyanqiang" if er else "weiqiang"},
            "west":  {"provider": wr, "kind": "houyanqiang" if wr else "weiqiang"},
        }

    # 用途(usage)：图谱声明「某角色在某情形下作何用途」——如四进院第二进院正位房作过厅。
    # role 不变、只多一个用途语义（故零几何漂移，可逆：usage=guoting ⇄「过厅」）。
    # ④ 不自行判断谁是过厅，只按 rules.usage 落字段（图谱驱动）。
    for u in (rules_doc.get("usage") or []):
        u_role, u_use, u_at, u_cond = u.get("role"), u.get("usage"), u.get("at"), u.get("when")
        if not u_role or not u_use or not u_at or not _jin_cond_ok(u_cond, jin):
            continue
        if u_at == "erjinyuan_zhengwei":
            target = (courtyards[1].get("enclosure") or {}) if len(courtyards) > 1 else {}
            nm = target.get("north")
            if nm and nm.get("role") == u_role:
                nm["usage"] = u_use

    return _wrap(jin, courtyards, rules_doc, type_doc, dict_doc)


def text_to_instance(text):
    """① 占位「理解层」：NL（含进数）-> 自包含 instance。后续替换为混元 LLM 原生生成。"""
    return build_instance(_parse_jin(text))


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
    返回 (plotted, norms, modus)；plotted[i] 含 {w,d,nd,sd,zc,north,south,east,west,c}。
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
        north, south, east, west = enc.get("north"), enc.get("south"), enc.get("east"), enc.get("west")
        ref = north or south or {}
        w = _dim(ref, "miankuo", 5) * modus
        nd = _dim(north, "jinshen", 0) * modus   # 缺房则进深记 0（无幽灵进深）
        sd = _dim(south, "jinshen", 0) * modus
        cdr = norms.get("courtDepthRatio", 0.6)
        if isinstance(cdr, dict):
            role = c.get("role")
            cdr_map = cdr.get("byRole", {})
            ratio = cdr_map.get(role, cdr.get("default", 0.6)) if role in cdr_map else cdr.get("default", 0.6)
        else:
            ratio = cdr
        court_depth = w * ratio   # 露天院落进深=面阔×按角色比例(front浅/main大/back中)
        d = nd + court_depth + sd
        plotted.append({"w": w, "d": d, "nd": nd, "sd": sd, "north": north, "south": south,
                        "east": east, "west": west, "c": c})

    total = sum(p["d"] for p in plotted)           # 院落间紧贴：双墙相邻无间隙(gap=0)
    z = -total / 2                                 # 序列1=最南(-Z)，序列N=最北(+Z)
    for p in plotted:
        p["zc"] = z + p["d"] / 2
        z += p["d"]
    return plotted, norms, modus


def compute_geometry(instance):
    """④ 几何计算：instance -> 构件列表。每个构件 = {role, center:{x,y,z}, size:{w,h,d}}。

    - 只读 instance（data + appliedRules + appliedType），不硬编码任何规制数字。
    - 输出是构件（连续几何），不是 box、不是空间。庭院虚空不输出。
    """
    plotted, norms, modus = _layout(instance)
    if not plotted:
        return []
    geometry = []
    for idx, p in enumerate(plotted):
        zc = p["zc"]
        w, d = p["w"], p["d"]
        nd, sd = p["nd"], p["sd"]

        if p["north"]:
            nrole = p["north"]
            if (nrole or {}).get("chuantang"):
                geometry.extend(_geo_zhengfang_chuantang(0, w, nd, zc + d / 2 - nd / 2, nrole, norms))
            else:
                # 北侧房屋朝南开口（庭院在南）——开口朝向由房屋所在侧决定，不靠角色名硬判
                geometry.extend(_geo_wing(0, w, nd, zc + d / 2 - nd / 2, nrole, "S", norms))
        if p["south"]:
            has_gate = bool((p["south"] or {}).get("gate"))
            geometry.extend(_geo_daozuo(0, w, sd, zc - d / 2 + sd / 2, p["south"], norms, has_gate))
        # 东西厢：长边沿 Z（面阔），厚沿 X（进深）。
        # Z 向填充「正房南檐 -> 倒座北檐」空隙，中心 = zc + (sd-nd)/2，
        # 使其与正房只在角上相接、体积不重叠（修此前 厢房/正房 空间重叠）。
        ew_z = zc + (sd - nd) / 2
        if p["east"]:
            ed = _dim(p["east"], "jinshen", 0) * modus
            el = _xiangfang_length(p["east"], norms, d, nd, sd, modus)
            geometry.extend(_geo_eastwest(+(w / 2 - ed / 2), el, ed, ew_z, p["east"], norms))
        if p["west"]:
            ed = _dim(p["west"], "jinshen", 0) * modus
            el = _xiangfang_length(p["west"], norms, d, nd, sd, modus)
            geometry.extend(_geo_eastwest(-(w / 2 - ed / 2), el, ed, ew_z, p["west"], norms))

        # 垂花门（仅一进→二进卡子墙正中、中轴线）：northGate 表示与前一院落的边界，门道南北贯通
        enc = p["c"].get("enclosure", {})
        if enc.get("northGate"):
            gz = zc + d / 2                         # 嵌在卡子墙缺口处(本院北墙)
            geometry.extend(_geo_chuihua(gz, w, _role_of(enc["northGate"], "chuihuamen"), norms))
        if enc.get("southGate"):
            gz = zc - d / 2
            geometry.extend(_geo_chuihua(gz, w, _role_of(enc["southGate"], "chuihuamen"), norms))

        # 围合构件（实体）：游廊 / 影壁
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
    return _resolve_boundary(geometry, norms)


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

        # —— 进院门：穿过本院的南界（首院=东南角宅门；余院=上一院北界的垂花门/穿堂）——
        if i == 0:
            if (enc.get("south") or {}).get("gate"):
                gz = z_south + sd / 2.0                    # 宅门门道轴线（嵌在倒座房进深内）
                path.append({"x": gate_x, "z": round(z_south - TOUR_OUTSIDE, 3),
                             "y": 0.0, "label": "宅门外"})
                path.append({"x": gate_x, "z": round(gz, 3), "y": TOUR_STEP, "label": "穿过大门"})
                z_in = z_south + sd + 0.6                  # 出倒座后檐入庭院，且避开影壁/厢房之南
                r = min(TOUR_CORNER_R, z_court - z_in - 0.45)   # 过渡半径受院深受限（外院很浅时会收小）
                if abs(gate_x) > 0.01 and r >= 0.25:       # 宅门偏东南，需横向折回中轴
                    # 只切「中轴」那个拐点：门后那个 90° 转没有余量可切——影壁正对宅门，
                    # 倒座房北檐与影壁南面之间只有约 0.95m 走道，往里切就退回门道/影壁里。
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
            nlabel = ROLE_LABELS.get((p["north"] or {}).get("role"), "院北")
            z_stop = z_north - nd - 1.2 if nd > 0 else z_north - 1.2
            path.append({"x": 0.0, "z": round(z_stop, 3), "y": 0.0, "label": f"{nlabel}前",
                         "pause": TOUR_PAUSE, "look": [0.0, round(z_north, 3)]})
            path.append({"x": 0.0, "z": round(z_stop + 0.7, 3), "y": 0.0, "label": "游毕",
                         "pause": TOUR_END_PAUSE,
                         "look": _glance(0.0, z_stop + 0.7, 0.0, +TOUR_LOOK_DEG, p["w"] / 2.0)})
        elif enc.get("northGate"):
            path.append({"x": 0.0, "z": round(z_north - TOUR_DOOR_DEPTH_HALF, 3), "y": 0.0,
                         "label": "垂花门前", "pause": TOUR_PAUSE,
                         "look": [0.0, round(z_north + 2.0, 3)]})
            path.append({"x": 0.0, "z": round(z_north, 3), "y": TOUR_STEP, "label": "穿过垂花门"})
        elif (p["north"] or {}).get("chuantang"):
            # 站名跟着图谱「用途」走：四进院第二进院正位房 usage=guoting（过厅，前堂），
            # 其余为普通正房。故不再硬编码「正房穿堂」——图谱一变，站名自动跟着变。
            nm = p["north"] or {}
            hall = USAGE_LABELS.get(nm.get("usage")) or ROLE_LABELS.get(nm.get("role"), "正房")
            path.append({"x": 0.0, "z": round(z_north - nd, 3), "y": TOUR_STEP,
                         "label": f"{hall}前檐"})
            path.append({"x": 0.0, "z": round(z_north - nd / 2.0, 3), "y": TOUR_STEP,
                         "label": f"穿过{hall}穿堂"})
            path.append({"x": 0.0, "z": round(z_north, 3), "y": TOUR_STEP,
                         "label": f"{hall}穿堂北口"})
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


def _geo_eastwest(cx, el, ed, zc, role_obj, norms):
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
    - 北/南按 gate 开缺（zhaimen 东南角 / chuihuamen·chuantang 中段）。
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
        elif gate in ("chuihuamen", "chuantang"):
            # 垂花门门洞宽 = 门体面阔(gateSpan)，与宅门同法从 norms 取；
            # 穿堂用房门洞口宽 norms.door.width（两者语义不同：门洞是墙上开缺，门体是一栋建筑）
            gs = (float(_norms_get(norms, ("chuihuamen", "gateSpan"), "垂花门面阔"))
                  if gate == "chuihuamen" else float(_norms_get(norms, ("door", "width"), "穿堂门洞宽")))
            gh = gs / 2
            l_seg = (0 - gh) - (-half)
            if l_seg > 0.01:
                out.append(_geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (0 + gh)
            if r_seg > 0.01:
                out.append(_geo_wall(gh + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        else:
            out.append(_geo_wall(0, zc_wall, w, H, T, "yuanqiang"))

    # 北墙：本进与后一进的分界（最北一进的北墙 = 整院北外墙）
    ns_wall(zN, (ring.get("north") or {}).get("gate"))
    # 南墙：仅最南一进(idx0)画 —— 即整院南外墙；其余进的南界由前一进北墙承担
    if draw_south:
        ns_wall(zS, (ring.get("south") or {}).get("gate"))
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
def _voxelize_component(g, vox):
    """构件(连续几何) -> 体素 BOX 网格（构件 : box = 图像 : 像素）。

    纯几何转换：把传入的构件实心切成边长为 vox 的体素网格。构件本身是实心还是
    空心围合（如房间拆成的墙/顶/地子构件），由 ④ 几何计算引擎决定，⑤ 不过问。
    label/color 由所属构件继承（点选任意体素都能识别其构件）。
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
    label = ROLE_LABELS.get(role, role)
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
    label/color 由所属构件继承。未来切 B-rep 只改此处，④ 不动。
    """
    boxes = []
    for g in geometry:
        boxes.extend(_voxelize_component(g, vox))
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
