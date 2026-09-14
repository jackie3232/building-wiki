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

# 体素边长（米）。越小越细、box 越多；越大越省、体素感越弱。MVP 提速版适中取值。
VOXEL_SIZE = 0.6

# role key -> 兜底中文名 / 颜色（⑤ 造型层使用，纯内置，不依赖外部词表）
ROLE_LABELS = {
    "zhengfang": "正房", "xiangfang": "厢房", "daozuofang": "倒座房",
    "houzhaofang": "后罩房", "chuihuamen": "垂花门", "erfang": "耳房",
    "youlang": "游廊", "yingbi": "影壁", "tingyuan": "庭院",
}
ROLE_COLORS = {
    "zhengfang": 0xC0504D, "xiangfang": 0xE0A030, "daozuofang": 0x4F81BD,
    "houzhaofang": 0x9B59B6, "chuihuamen": 0x82A33A, "erfang": 0x9B59B6,
    "youlang": 0x808080, "yingbi": 0xB0A040, "tingyuan": 0xCFCFCF,
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


def _cy(seq, name, north=None, south=None, east=None, west=None,
        northGate=None, southGate=None, peripheral=None):
    enc = {"relation": "weihe"}
    if north: enc["north"] = north
    if south: enc["south"] = south
    if east: enc["east"] = east
    if west: enc["west"] = west
    if northGate: enc["northGate"] = northGate
    if southGate: enc["southGate"] = southGate
    c = {"id": f"cy{seq}", "name": name, "sequence": seq,
         "enclosure": enc, "center": {"role": "tingyuan"}}
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


def build_instance(jin):
    """① 占位：按进数合成自包含 instance（读知识中心 type+rules）。"""
    rules_doc = load_json(os.path.join(KNOWLEDGE_DIR, "siheyuan.rules"))
    norms = rules_doc.get("norms", {})
    courtyards = []

    if jin <= 1:
        courtyards.append(_cy(1, "正院",
            north=_room("zhengfang", norms), south=_room("daozuofang", norms),
            east=_room("xiangfang", norms), west=_room("xiangfang", norms),
            peripheral=[{"role": "youlang"}, {"role": "yingbi"}]))
    elif jin == 2:
        courtyards.append(_cy(1, "外院", south=_room("daozuofang", norms),
                              northGate={"role": "chuihuamen"}))
        courtyards.append(_cy(2, "内院", north=_room("zhengfang", norms),
            east=_room("xiangfang", norms), west=_room("xiangfang", norms),
            peripheral=[{"role": "youlang"}, {"role": "yingbi"}]))
    else:
        # jin >= 3
        courtyards.append(_cy(1, "外院", south=_room("daozuofang", norms),
                              northGate={"role": "chuihuamen"}))
        for k in range(2, jin):
            peripheral = [{"role": "youlang"}, {"role": "yingbi"}] if k == 2 else None
            courtyards.append(_cy(k, f"内院{k-1}",
                north=_room("zhengfang", norms), east=_room("xiangfang", norms),
                west=_room("xiangfang", norms), northGate={"role": "chuihuamen"},
                peripheral=peripheral))
        courtyards.append(_cy(jin, "正院",
            north=_room("houzhaofang", norms), east=_room("xiangfang", norms),
            west=_room("xiangfang", norms)))

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
    for c in courtyards:
        enc = c.get("enclosure", {})
        north, south, east, west = enc.get("north"), enc.get("south"), enc.get("east"), enc.get("west")
        ref = north or south or {}
        w = _dim(ref, "miankuo", 5) * modus
        north_depth = _dim(north, "jinshen", 3) * modus
        south_depth = _dim(south, "jinshen", 2) * modus
        court_depth = w * 0.6                      # 露天院落进深（MVP 占位）
        d = north_depth + court_depth + south_depth
        plotted.append({"w": w, "d": d, "north": north, "south": south,
                        "east": east, "west": west, "c": c})

    gap = 2.0                                      # 院落间垂花门通道
    total = sum(p["d"] for p in plotted) + gap * max(n - 1, 0)
    z = -total / 2                                 # 序列1=最南(-Z)，序列N=最北(+Z)
    geometry = []
    for p in plotted:
        zc = z + p["d"] / 2
        w, d = p["w"], p["d"]
        nd = _dim(p["north"], "jinshen", 3) * modus
        sd = _dim(p["south"], "jinshen", 2) * modus

        if p["north"]:
            geometry.append(_geo_wing(0, w, nd, zc + d / 2 - nd / 2, p["north"]))
        if p["south"]:
            geometry.append(_geo_wing(0, w, sd, zc - d / 2 + sd / 2, p["south"]))
        # 东西厢：长边沿 Z（面阔），厚沿 X（进深）。
        # Z 向填充「正房南檐 -> 倒座北檐」空隙，中心 = zc + (sd-nd)/2，
        # 使其与正房只在角上相接、体积不重叠（修此前 厢房/正房 空间重叠）。
        ew_z = zc + (sd - nd) / 2
        if p["east"]:
            ed = _dim(p["east"], "jinshen", 2) * modus
            el = d - nd - sd
            geometry.append(_geo_eastwest(+(w / 2 - ed / 2), el, ed, ew_z, p["east"]))
        if p["west"]:
            ed = _dim(p["west"], "jinshen", 2) * modus
            el = d - nd - sd
            geometry.append(_geo_eastwest(-(w / 2 - ed / 2), el, ed, ew_z, p["west"]))

        # 垂花门（院落分隔 gate）：northGate 表示与前一院落的边界，每边界一个
        enc = p["c"].get("enclosure", {})
        if enc.get("northGate"):
            geometry.append(_geo_gate(zc + d / 2, w, _role_of(enc["northGate"], "chuihuamen")))
        if enc.get("southGate"):
            geometry.append(_geo_gate(zc - d / 2, w, _role_of(enc["southGate"], "chuihuamen")))

        # 围合构件（实体）：游廊 / 影壁
        for per in (p["c"].get("peripheral") or []):
            if not isinstance(per, dict):
                continue
            prole = per.get("role")
            if prole == "youlang":
                geometry.append(_geo_youlang(w, nd, zc, d))
            elif prole == "yingbi":
                geometry.append(_geo_yingbi(w, sd, zc, d))

        z += p["d"] + gap
    return geometry


def _geo_wing(cx, w, depth, zc, role_obj):
    """南北向屋翼：长边沿 X（面阔），厚沿 Z（进深）"""
    return {"role": role_obj.get("role"),
            "center": {"x": round(cx, 3), "y": WING_HEIGHT / 2, "z": round(zc, 3)},
            "size": {"w": round(w, 3), "h": WING_HEIGHT, "d": round(depth, 3)}}


def _geo_eastwest(cx, el, ed, zc, role_obj):
    """东西厢：长边沿 Z（面阔），厚沿 X（进深）"""
    return {"role": role_obj.get("role"),
            "center": {"x": round(cx, 3), "y": WING_HEIGHT / 2, "z": round(zc, 3)},
            "size": {"w": round(ed, 3), "h": WING_HEIGHT, "d": round(el, 3)}}


def _geo_gate(zc, w, role):
    """垂花门：窄门洞示意（占位）"""
    return {"role": role,
            "center": {"x": 0, "y": WING_HEIGHT / 2, "z": round(zc, 3)},
            "size": {"w": round(min(w * 0.25, 4.0), 3), "h": WING_HEIGHT, "d": 1.0}}


def _geo_youlang(w, nd, zc, d):
    """游廊：正房前檐的窄廊（占位）"""
    depth = 1.2
    zpos = zc + d / 2 - nd - depth / 2
    return {"role": "youlang",
            "center": {"x": 0, "y": PERIPH_HEIGHT / 2, "z": round(zpos, 3)},
            "size": {"w": round(w * 0.85, 3), "h": PERIPH_HEIGHT, "d": depth}}


def _geo_yingbi(w, sd, zc, d):
    """影壁：入口处的屏墙（占位）"""
    bw = 3.0
    zpos = zc - d / 2 + sd + 1.2
    return {"role": "yingbi",
            "center": {"x": round(w / 2 - bw / 2 - 0.5, 3), "y": PERIPH_HEIGHT / 2, "z": round(zpos, 3)},
            "size": {"w": bw, "h": PERIPH_HEIGHT, "d": 0.5}}


# ---------------- ⑤ 几何造型引擎：构件 -> 体素 BOX 清单 ----------------
def _voxelize_component(g, vox):
    """构件(连续几何) -> 体素 BOX 网格（构件 : box = 图像 : 像素）。

    沿 X/Y/Z 把构件实心切成边长为 vox 的体素网格，每体素是一个小 box；
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
