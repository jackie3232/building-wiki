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

设计铁律（见 架构设计总览.md §7/§9/§14、几何计算引擎IO契约.md）：
- 零坐标：instance 不含 x/y/z；④ 据「间」模数与拓扑算绝对坐标（④ 本职）。
- ④ 只吃 instance（data+appliedRules），MODUS 等换算标准从 appliedRules.norms 取，不硬编码。
- 输出是「构件」不是「box」也不是「空间」；构件 : box = 图像 : 像素（box 由 ⑤ 多体素化）。
- ⑤ 只做造型策略（MVP = 无 B-rep 的 BOX 体素），未来可切 Box/Brep 等基元，不污染 ④。
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # server/
KNOWLEDGE_DIR = os.path.join(BASE, "knowledge")
DATA_DIR = os.path.join(BASE, "data", "instances")

# —— MVP 占位模数（1 间 = 3.3 m）。优先从 instance.appliedRules.norms.modus 取，此处为兜底。——
MODUS = 3.3
WING_HEIGHT = 3.3
PERIPH_HEIGHT = 2.5          # 游廊/影壁等围合构件占位高度（MVP 占位）
YUANQIANG_HEIGHT = 2.2       # 外围院墙占位高度（MVP 占位，低于房屋）
WALL_THICKNESS = 0.3          # 房间围合墙/顶/地厚度（米，真实几何量；⑤ 体素化后约 1 个体素厚）
DOOR_WIDTH = 1.6              # 房门洞口宽（米）
DOOR_HEIGHT = 2.1             # 房门洞口高（米，自地面起）
ZHAMEN_GATE_SPAN = 3.0       # 大门(宅门)门道面阔（米，MVP 占位；优先从 norms.zhaimen.gateSpan 取）
ZHAMEN_HEIGHT = 4.2          # 大门门楼屋顶高度（米，高于普通房屋，MVP 占位；优先从 norms.zhaimen.height 取）
ZHAMEN_EAST_MARGIN = 0.8      # 大门东边缘距院墙东端留白（米），使东南角院墙完整闭合
CHUIHUA_GATE_SPAN = 3.0       # 垂花门面阔（米，约一间；优先从 norms.chuihuamen.gateSpan 取）

# 体素边长（米）。越小越细、box 越多；越大越省、体素感越弱。MVP 提速版适中取值。
VOXEL_SIZE = 0.6

# role key -> 兜底中文名 / 颜色（⑤ 造型层使用，纯内置，不依赖外部词表）
ROLE_LABELS = {
    "zhengfang": "正房", "xiangfang": "厢房", "daozuofang": "倒座房",
    "houzhaofang": "后罩房", "chuihuamen": "垂花门", "erfang": "耳房",
    "youlang": "游廊", "yingbi": "影壁", "tingyuan": "庭院", "yuanqiang": "院墙",
    "zhaimen": "大门",
}
ROLE_COLORS = {
    "zhengfang": 0xC0504D, "xiangfang": 0xE0A030, "daozuofang": 0x4F81BD,
    "houzhaofang": 0x9B59B6, "chuihuamen": 0x82A33A, "erfang": 0x9B59B6,
    "youlang": 0x808080, "yingbi": 0xB0A040, "tingyuan": 0xCFCFCF, "yuanqiang": 0x7F7F7F,
    "zhaimen": 0x8B4513,
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


def _room(role, norms):
    n = norms.get(role, {}) or {}
    return {"role": role,
            "miankuo": n.get("miankuo", 5),
            "jinshen": n.get("jinshen", 3)}


def _south_with_gate(norms):
    """最外院(sequence==1)倒座房：附大门(zhaimen)，使 ④ 渲染东南角宅门。"""
    r = _room("daozuofang", norms)
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
    """规则库 -> appliedRules 快照（深拷贝，保证 instance 自包含、可独立复现）。"""
    snap = json.loads(json.dumps(rules_doc))
    snap.setdefault("norms", {})
    snap["norms"].setdefault("modus", MODUS)
    return snap


def _wrap(jin, courtyards, rules_doc):
    data = {"type": "siheyuan", "jin": jin, "courtyards": courtyards}
    return {
        "meta": {
            "type": "siheyuan",
            "desc": f"北京{jin}进四合院实例（由类型图谱+规则库合成，工程文件·自包含）",
            "generatedBy": "build_instance (① placeholder)",
            "zeroCoord": True,
        },
        "data": data,
        "appliedRules": _snapshot_rules(rules_doc),
    }


def build_instance(jin, omit=None):
    """① 占位：按进数合成自包含 instance（读知识中心 type+rules）。"""
    rules_doc = load_json(os.path.join(KNOWLEDGE_DIR, "siheyuan.rules"))
    norms = rules_doc.get("norms", {})
    courtyards = []

    if jin <= 1:
        courtyards.append(_cy(1, "正院",
            north=_room("zhengfang", norms), south=_south_with_gate(norms),
            east=_room("xiangfang", norms), west=_room("xiangfang", norms),
            peripheral=[{"role": "youlang"}, {"role": "yingbi"}], perimeter=True))
    elif jin == 2:
        courtyards.append(_cy(1, "外院", south=_south_with_gate(norms),
                              northGate={"role": "chuihuamen"}, perimeter=True))
        courtyards.append(_cy(2, "内院", north=_room("zhengfang", norms),
            east=_room("xiangfang", norms), west=_room("xiangfang", norms),
            peripheral=[{"role": "youlang"}, {"role": "yingbi"}], perimeter=True))
    else:
        # jin >= 3：仅一进→二进设垂花门；内院正房明间为穿堂(南北贯通)，连通下一进；
        #           末进为后院(后罩房)，经穿堂/夹道连通，不设独立门楼。
        courtyards.append(_cy(1, "外院", south=_south_with_gate(norms),
                              northGate={"role": "chuihuamen"}, perimeter=True))
        for k in range(2, jin):
            # 内院：正房明间(中央开间)为穿堂，南北开门连通后院；其余院落边界不设垂花门
            zf = _room("zhengfang", norms)
            zf["chuantang"] = True
            peripheral = [{"role": "youlang"}, {"role": "yingbi"}] if k == 2 else None
            courtyards.append(_cy(k, f"内院{k-1}",
                north=zf, east=_room("xiangfang", norms),
                west=_room("xiangfang", norms), peripheral=peripheral, perimeter=True))
        courtyards.append(_cy(jin, "后院",
            north=_room("houzhaofang", norms), east=_room("xiangfang", norms),
            west=_room("xiangfang", norms), perimeter=True))

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

    return _wrap(jin, courtyards, rules_doc)


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


def compute_geometry(instance):
    """④ 几何计算：instance -> 构件列表。每个构件 = {role, center:{x,y,z}, size:{w,h,d}}。

    - 只读 instance（data + appliedRules）；MODUS 从 appliedRules.norms 取。
    - 输出是构件（连续几何），不是 box、不是空间。庭院虚空不输出。
    """
    data = instance.get("data", instance)
    applied = instance.get("appliedRules", {})
    norms = applied.get("norms", {}) or {}
    modus = norms.get("modus", MODUS)

    courtyards = sorted(data.get("courtyards", []), key=lambda c: c.get("sequence", 0))
    n = len(courtyards)
    if n == 0:
        return []

    # 先算每院占地：w 沿 X（面阔），d 沿 Z（进深）
    plotted = []
    for idx, c in enumerate(courtyards):
        enc = c.get("enclosure", {})
        north, south, east, west = enc.get("north"), enc.get("south"), enc.get("east"), enc.get("west")
        ref = north or south or {}
        w = _dim(ref, "miankuo", 5) * modus
        north_depth = _dim(north, "jinshen", 0) * modus   # 缺房则进深记 0（无幽灵进深）
        south_depth = _dim(south, "jinshen", 0) * modus
        cdr = norms.get("courtDepthRatio", 0.6)
        if isinstance(cdr, dict):
            role = c.get("role")
            cdr_map = cdr.get("byRole", {})
            ratio = cdr_map.get(role, cdr.get("default", 0.6)) if role in cdr_map else cdr.get("default", 0.6)
        else:
            ratio = cdr
        court_depth = w * ratio   # 露天院落进深=面阔×按角色比例(front浅/main大/back中)
        d = north_depth + court_depth + south_depth
        plotted.append({"w": w, "d": d, "north": north, "south": south,
                        "east": east, "west": west, "c": c})

    gap = 0.0                                      # 院落间紧贴：各院独立围墙，双墙相邻无间隙
    total = sum(p["d"] for p in plotted) + gap * max(n - 1, 0)
    z = -total / 2                                 # 序列1=最南(-Z)，序列N=最北(+Z)
    geometry = []
    for idx, p in enumerate(plotted):
        zc = z + p["d"] / 2
        w, d = p["w"], p["d"]
        nd = _dim(p["north"], "jinshen", 0) * modus
        sd = _dim(p["south"], "jinshen", 0) * modus

        if p["north"]:
            nrole = p["north"]
            if (nrole or {}).get("chuantang"):
                geometry.extend(_geo_zhengfang_chuantang(0, w, nd, zc + d / 2 - nd / 2, nrole, norms))
            else:
                geometry.extend(_geo_wing(0, w, nd, zc + d / 2 - nd / 2, nrole))
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
            geometry.extend(_geo_eastwest(+(w / 2 - ed / 2), el, ed, ew_z, p["east"]))
        if p["west"]:
            ed = _dim(p["west"], "jinshen", 0) * modus
            el = _xiangfang_length(p["west"], norms, d, nd, sd, modus)
            geometry.extend(_geo_eastwest(-(w / 2 - ed / 2), el, ed, ew_z, p["west"]))

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
                geometry.extend(_geo_youlang(w, nd, zc, d))
            elif prole == "yingbi":
                geometry.append(_geo_yingbi(w, sd, zc, d))

        # 院墙环（boundarySegmentRealization）：先画完整一圈墙、门(gate)开缺；
        # 贴边建筑（后檐墙/山墙）的实现不在此预判——统一交给末尾 _resolve_boundary 去重。
        if p["c"].get("perimeter"):
            geometry.extend(_geo_wall_ring(p["c"], w, zc, d, norms, draw_south=(idx == 0)))

        z += p["d"] + gap
    # 边界去重：同一条墙线上建筑墙优先于独立院墙(yuanqiang)，被覆盖的院墙段按区间相减掉。
    return _resolve_boundary(geometry)


def _geo_slab(role, cx, cy, cz, w, h, d):
    """单块板状构件（地面/屋顶/单面墙）。"""
    return {"role": role,
            "center": {"x": round(cx, 3), "y": round(cy, 3), "z": round(cz, 3)},
            "size": {"w": round(w, 3), "h": round(h, 3), "d": round(d, 3)}}


def _geo_room(role, cx, cz, W, H, D, open_side=None):
    """房间 = 围合结构：地面 + 屋顶 + 四壁（朝庭院一侧留门洞，而非整面掏空），内部空心。

    ④ 本职：把房间拆成可独立体素化的子构件，而非塞一整个实心长方体。
    open_side ∈ {'N','S','E','W'} 或其列表：该侧（们）朝庭院，墙面居中留门洞。
    传列表（如 ['S','N']）可表达「贯通门道」：南北双向开口。
    """
    t = WALL_THICKNESS
    floor_top = t
    roof_bot = H - t
    wall_h = roof_bot - floor_top                       # 墙高（地面顶 -> 屋顶底）
    open_set = {open_side} if isinstance(open_side, str) else set(open_side or [])
    comps = [
        _geo_slab(role, cx, t / 2, cz, W, t, D),            # 地面
        _geo_slab(role, cx, H - t / 2, cz, W, t, D),        # 屋顶
    ]
    if "N" not in open_set:
        comps.append(_geo_slab(role, cx, H / 2, cz + D / 2 - t / 2, W, wall_h, t))   # 北墙
    if "S" not in open_set:
        comps.append(_geo_slab(role, cx, H / 2, cz - D / 2 + t / 2, W, wall_h, t))   # 南墙
    if "E" not in open_set:
        comps.append(_geo_slab(role, cx + W / 2 - t / 2, H / 2, cz, t, wall_h, D))   # 东墙
    if "W" not in open_set:
        comps.append(_geo_slab(role, cx - W / 2 + t / 2, H / 2, cz, t, wall_h, D))   # 西墙
    for s in open_set:
        comps.extend(_geo_front_wall(role, cx, cz, W, H, D, t, wall_h, floor_top, roof_bot, s))
    return comps


def _geo_gate_tower(role, cx, cz, W, base_h, top_h, D):
    """门楼：坐落在门道屋顶之上的一段抬高墙冠 + 顶，使宅门明显高于倒座房。

    ④ 本职：门楼是独立子构件，纯几何；⑤ 实心体素化即可。
    base_h=门道屋顶高(3.3m)，top_h=门楼屋顶高(4.2m)，band=抬高的 0.9m 墙冠。
    """
    if top_h <= base_h:
        return []
    t = WALL_THICKNESS
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


def _geo_front_wall(role, cx, cz, W, H, D, t, wall_h, floor_top, roof_bot, open_side):
    """朝庭院的墙：居中留门洞（宽 DOOR_WIDTH、高 DOOR_HEIGHT），由左右墙段+门楣组成。

    左右墙段为整高实体，门洞上方用门楣封顶；门洞本身不生成体素（即门）。
    """
    face_span = W if open_side in ("N", "S") else D
    dw = min(DOOR_WIDTH, face_span - 2 * t)     # 门洞宽（不超过墙面净宽）
    dh = min(DOOR_HEIGHT, wall_h)               # 门洞高
    lx = dw / 2
    door_top = floor_top + dh
    lintel_h = roof_bot - door_top
    y_lintel = (door_top + roof_bot) / 2
    out = []
    if open_side in ("N", "S"):
        z = cz + (D / 2 - t / 2) if open_side == "N" else cz - (D / 2 - t / 2)
        seg = W / 2 - lx                                  # 单侧墙段宽
        out.append(_geo_slab(role, cx - (lx + seg / 2), H / 2, z, seg, wall_h, t))   # 左墙段
        out.append(_geo_slab(role, cx + (lx + seg / 2), H / 2, z, seg, wall_h, t))   # 右墙段
        if lintel_h > 0:
            out.append(_geo_slab(role, cx, y_lintel, z, dw, lintel_h, t))            # 门楣
    else:  # E / W
        x = cx + (W / 2 - t / 2) if open_side == "E" else cx - (W / 2 - t / 2)
        seg = D / 2 - lx                                  # 单侧墙段深
        out.append(_geo_slab(role, x, H / 2, cz - (lx + seg / 2), t, wall_h, seg))   # 左墙段
        out.append(_geo_slab(role, x, H / 2, cz + (lx + seg / 2), t, wall_h, seg))   # 右墙段
        if lintel_h > 0:
            out.append(_geo_slab(role, x, y_lintel, cz, t, lintel_h, dw))            # 门楣
    return out


def _geo_wing(cx, w, depth, zc, role_obj):
    """南北向屋翼（正房/倒座/后罩）：长边沿 X（面阔），厚沿 Z（进深）。
    房间=围合结构，朝庭院一侧留敞口：正房/后罩朝南('S')，倒座朝北('N')。"""
    role = role_obj.get("role")
    open_side = "S" if role in ("zhengfang", "houzhaofang") else "N"
    return _geo_room(role, cx, zc, w, WING_HEIGHT, depth, open_side)


def _geo_daozuo(cx, w, sd, zc, role_obj, norms, has_gate):
    """倒座房：最外院(含宅门)拆为「西段普通倒座房 + 东端大门间(门道+门楼)」；
    非最外院则整排普通倒座房。④ 本职：围合结构算清，⑤ 不过问空心。

    - 西段：普通倒座房，朝北('N')留门洞，居中偏西。
    - 东端大门间：门道(朝东'E'留大门洞)+ 抬高门楼(屋顶高于普通房)，位于院落东南角。
    """
    if not has_gate:
        return _geo_wing(cx, w, sd, zc, role_obj)
    zcfg = (norms.get("zhaimen", {}) or {})
    gs = round(float(zcfg.get("gateSpan", ZHAMEN_GATE_SPAN)), 3)
    gh = round(float(zcfg.get("height", ZHAMEN_HEIGHT)), 3)
    gs = round(min(gs, w - 0.6), 3)                       # 大门段不超倒座房总面阔
    gate_center = round(cx + (w / 2 - gs / 2 - ZHAMEN_EAST_MARGIN), 3)  # 东南角留白
    seg_right = gate_center - gs / 2                      # 西段右边界（=门左缘）
    x_main = round((-w / 2 + seg_right) / 2, 3)
    w_main = round(seg_right + w / 2, 3)
    comps = []
    # 西段普通倒座房（朝北留门洞，与内院相对）
    comps.extend(_geo_room(role_obj.get("role"), x_main, zc, w_main, WING_HEIGHT, sd, "N"))
    # 东端大门：门道(同高 3.3m，南=街门、北=内院，双向贯通) + 门楼(屋顶抬高至 4.2m)
    comps.extend(_geo_room("zhaimen", gate_center, zc, gs, WING_HEIGHT, sd, ["S", "N"]))
    comps.extend(_geo_gate_tower("zhaimen", gate_center, zc, gs, WING_HEIGHT, gh, sd))
    return comps


def _geo_eastwest(cx, el, ed, zc, role_obj):
    """东西厢：长边沿 Z（面阔），厚沿 X（进深）。
    房间=围合结构，朝庭院中心留敞口：东厢朝西('W')，西厢朝东('E')。"""
    role = role_obj.get("role")
    open_side = "W" if cx > 0 else "E"
    return _geo_room(role, cx, zc, ed, WING_HEIGHT, el, open_side)


def _xiangfang_length(role_obj, norms, d, nd, sd, modus):
    """④ 厢房沿庭院方向(Z)长度：读 rules.layout.xiangfang 约束，不再硬编码填满庭院。

    - lengthMode=miankuo：长度取自身面阔(间数×modus)，而非 d-nd-sd
    - aisle：南北与正房/倒座各留通道，使中央庭院完整保留
    - zAlign=center 由调用方 ew_z 实现（ew_z 已是庭院净深中心）
    """
    layout = (norms.get("layout", {}) or {}).get("xiangfang", {}) or {}
    aisle = layout.get("aisle", 1.5)
    own = _dim(role_obj, "miankuo", 3) * modus       # 自身面阔(3间×3.3)
    court_net = d - nd - sd                          # 庭院净深
    return round(min(own, court_net - 2 * aisle), 3)


def _geo_zhengfang_chuantang(cx, w, depth, zc, role_obj, norms):
    """正房明间(中央开间)为穿堂：南北双向开门，连通内院与后院；左右次间为普通房间(仅朝南开敞)。

    ④ 本职：把正房拆成 3 个开间子构件 —— 左右次间(朝南留门洞) + 中央明间(南北贯通门道)。
    门道方向由 KB 的 chuantang 标记驱动（即正房明间过厅），⑤ 实心体素化即可。
    """
    role = role_obj.get("role", "zhengfang")
    miankuo = _dim(role_obj, "miankuo", 5)
    bay = (w / miankuo) if miankuo else (w / 5)      # 每间面阔(米)
    central = min(bay, w * 0.4)                       # 中央明间(约 1 间)，作穿堂
    side = (w - central) / 2
    comps = []
    if side > 0.2:
        comps.extend(_geo_room(role, cx - (central / 2 + side / 2), zc, side, WING_HEIGHT, depth, "S"))
        comps.extend(_geo_room(role, cx + (central / 2 + side / 2), zc, side, WING_HEIGHT, depth, "S"))
    # 中央明间 = 穿堂（南北贯通）
    comps.extend(_geo_room(role, cx, zc, central, WING_HEIGHT, depth, ["S", "N"]))
    return comps


def _geo_chuihua(zc, w, role, norms):
    """垂花门(二门)：卡子墙正中、中轴线，门道南北贯通(门洞)，门楼略抬高。

    ④ 本职：门道为围合结构(南北开门)，门楼独立子构件；⑤ 实心体素化即可。
    不再用实心方块占位（此前错误）。
    门道面阔 gs 取自 norms.chuihuamen.gateSpan，与 _geo_wall_ring 开洞同源，
    保证「门体宽 == 卡子墙洞口宽」，两侧不留通缝。
    """
    cfg = (norms.get("chuihuamen", {}) or {})
    gs = round(float(cfg.get("gateSpan", CHUIHUA_GATE_SPAN)), 3)
    gh = round(float(cfg.get("height", WING_HEIGHT)), 3)
    depth = 1.2
    comps = _geo_room(role, 0, zc, gs, WING_HEIGHT, depth, ["S", "N"])   # 门道南北贯通
    if gh > WING_HEIGHT + 0.05:
        comps.extend(_geo_gate_tower(role, 0, zc, gs, WING_HEIGHT, gh, depth))   # 门楼略高
    return comps


def _geo_youlang(w, nd, zc, d):
    """游廊：正房前檐的柱廊——柱列 + 廊顶，通透无实墙（抄手游廊的直段）。

    廊与院墙不同：不围合，只提供有顶通道。中轴穿堂口断开 DOOR_WIDTH，
    让出正房明间南北通行的门道（否则就成了堵在正房前的一堵墙）。
    """
    out = []
    depth = 1.2
    zpos = zc + d / 2 - nd - depth / 2
    half = (w * 0.85) / 2.0
    gap = DOOR_WIDTH
    top_h, col = 0.2, WALL_THICKNESS
    for a, b in ((-half, -gap / 2.0), (gap / 2.0, half)):    # 左右两段，中间让开穿堂
        seg = b - a
        if seg <= 0.05:
            continue
        # 廊顶：薄板，跨该段
        out.append(_geo_slab("youlang", (a + b) / 2.0, PERIPH_HEIGHT - top_h / 2.0,
                             zpos, seg, top_h, depth))
        # 柱列：两端 + 按约 2.5m 间距均布
        n = max(2, int(round(seg / 2.5)) + 1)
        for i in range(n):
            x = a + seg * i / (n - 1)
            out.append(_geo_slab("youlang", x, (PERIPH_HEIGHT - top_h) / 2.0,
                                 zpos, col, PERIPH_HEIGHT - top_h, col))
    return out


def _geo_yingbi(w, sd, zc, d):
    """影壁：入口处的屏墙（占位）"""
    bw = 3.0
    zpos = zc - d / 2 + sd + 1.2
    return {"role": "yingbi",
            "center": {"x": round(w / 2 - bw / 2 - 0.5, 3), "y": PERIPH_HEIGHT / 2, "z": round(zpos, 3)},
            "size": {"w": bw, "h": PERIPH_HEIGHT, "d": 0.5}}


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
    wh = (norms.get("wall") or {})
    H = float(wh.get("height", YUANQIANG_HEIGHT))
    T = float(wh.get("thickness", 0.4))
    t = WALL_THICKNESS
    half = w / 2 - t / 2                     # 东西墙中心 X（与厢房外墙同一墙面线）
    zN = zc + d / 2 - t / 2                 # 北墙与正房/后罩房后檐墙共线
    zS = zc - d / 2 + t / 2                 # 南墙与倒座后檐墙共线
    out = []

    def ns_wall(zc_wall, gate):
        if gate == "zhaimen":
            gs = float((norms.get("zhaimen", {}) or {}).get("gateSpan", ZHAMEN_GATE_SPAN))
            gx = round(w / 2 - gs / 2 - ZHAMEN_EAST_MARGIN, 3)
            gh = gs / 2
            l_seg = (gx - gh) - (-half)
            if l_seg > 0.01:
                out.append(_geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (gx + gh)
            if r_seg > 0.01:
                out.append(_geo_wall((gx + gh) + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        elif gate in ("chuihuamen", "chuantang"):
            # 垂花门门洞宽 = 门体面阔(gateSpan)，与宅门同法从 norms 取；
            # 穿堂仍用房门洞口宽 DOOR_WIDTH（两者尺寸语义不同，不共用同一常量）
            gs = (float((norms.get("chuihuamen", {}) or {}).get("gateSpan", CHUIHUA_GATE_SPAN))
                  if gate == "chuihuamen" else DOOR_WIDTH)
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


def _resolve_boundary(components):
    """边界墙去重（boundarySegmentRealization 的几何实现）。

    同一条共线墙线上，建筑墙(后檐墙/山墙, pri=1)优先于独立院墙(yuanqiang, pri=0)：
    把被建筑覆盖的区间从 yuanqiang 段中【区间相减】掉（非整段删），保留真正空档。

    建筑自身的门/窗洞口（由矮薄的门楣标记，见 _geo_front_wall）一并算作「建筑覆盖段」——
    洞口是建筑的开口，独立院墙不得残留在洞口中（否则会把穿堂/门洞堵死）。
    resolver 只看真实几何覆盖，不预判任何建筑位置——增删建筑时该侧院墙自动补/让。
    """
    thin = WALL_THICKNESS + 0.15                  # 细墙/门楣判定容差（墙厚 0.3~0.4）
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
