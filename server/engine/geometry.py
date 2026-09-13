"""
④ 几何计算引擎 + ⑤ 几何造型引擎(BOX 出口)
------------------------------------------------
输入 ：实例图谱（数据中心：server/data/instances/*.json）
       其结构继承 siheyuan.type.json、受 siheyuan.rules 约束、用词表 dict.json
输出 ：体素 BOX 清单（场景坐标：Y-up，单位米）
       每个 box = {x,y,z, w,h,d, role, label, color}

设计铁律（见 架构设计总览.md §7/§9）：
- 零坐标：实例图谱本身不含 x/y/z；本引擎据「间」模数与组合拓扑算出相对位置。
- 与体素无关：④只算相对位置清单；⑤把它落成 box。两层在此合并于同一模块，
  但函数分离（compute_layout / _wing），便于后续把 ④ 抽成可替换后端。
- 模数换算（MODUS / WING_HEIGHT）为 MVP 占位，待文化建设校准真实古建数字。
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # server/
KNOWLEDGE_DIR = os.path.join(BASE, "knowledge")
DATA_DIR = os.path.join(BASE, "data", "instances")

MODUS = 3.3          # 1 间 = 3.3 m（MVP 占位，待文化建设校准）
WING_HEIGHT = 3.3    # 屋高 m（MVP 占位）

# role key -> 兜底中文名（优先读 dict.json）
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


def _load_dict_labels():
    try:
        d = json.load(open(os.path.join(KNOWLEDGE_DIR, "dict.json"), encoding="utf-8"))
        m = {}
        for cat, items in d.items():
            if cat == "meta":
                continue
            if not isinstance(items, dict):
                continue
            for name, v in items.items():
                if isinstance(v, dict) and "key" in v:
                    m[v["key"]] = name
        return m
    except Exception:
        return {}


_LABELS = _load_dict_labels()


def label_of(role):
    return _LABELS.get(role) or ROLE_LABELS.get(role) or role


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_seed():
    return load_json(os.path.join(DATA_DIR, "siheyuan.instance.json"))


def text_to_instance(text):
    """
    MVP 占位「理解层」：关键词 -> 种子实例。
    ⚠️ 后续由 ① LLM 原生层（混元 hy3-preview）替换：吃知识中心上下文 ->
       受类型图谱 schema 约束的实例图谱 JSON。此处仅保证 NL 输入框现在就能跑通。
    """
    return load_seed()


# ---------------- ④ 几何计算：实例图谱 -> 相对位置清单（米, Y-up） ----------------
def compute_layout(instance):
    site = instance.get("site", {})
    courtyards = sorted(site.get("courtyards", []), key=lambda c: c.get("sequence", 0))
    n = len(courtyards)
    if n == 0:
        return []

    plotted = []
    for c in courtyards:
        enc = c.get("enclosure", {})
        north = enc.get("north")
        south = enc.get("south")
        east = enc.get("east")
        west = enc.get("west")
        ref_wing = north or south or {}
        width_bays = ref_wing.get("miankuo", 5)
        w = width_bays * MODUS
        north_depth = (north.get("jinshen", 3) if north else 0) * MODUS
        south_depth = (south.get("jinshen", 2) if south else 0) * MODUS
        court_depth = w * 0.6                      # 露天院落进深（MVP 占位）
        d = north_depth + court_depth + south_depth
        plotted.append({
            "w": w, "d": d, "north": north, "south": south,
            "east": east, "west": west, "c": c,
        })

    gap = 2.0                                      # 院落间垂花门通道
    total = sum(p["d"] for p in plotted) + gap * max(n - 1, 0)
    z = -total / 2                                 # 序列1=最南(-Z)，序列N=最北(+Z)
    boxes = []
    for i, p in enumerate(plotted):
        zc = z + p["d"] / 2
        w, d = p["w"], p["d"]

        if p["north"]:
            nd = p["north"].get("jinshen", 3) * MODUS
            boxes.append(_wing(0, w, nd, zc + d / 2 - nd / 2, p["north"]))
        if p["south"]:
            sd = p["south"].get("jinshen", 2) * MODUS
            boxes.append(_wing(0, w, sd, zc - d / 2 + sd / 2, p["south"]))
        if p["east"]:
            ed = p["east"].get("jinshen", 2) * MODUS
            el = d - (p["north"].get("jinshen", 3) if p["north"] else 0) * MODUS \
                  - (p["south"].get("jinshen", 2) if p["south"] else 0) * MODUS
            boxes.append(_wing_eastwest(+(w / 2 - ed / 2), el, ed, zc, p["east"]))
        if p["west"]:
            ed = p["west"].get("jinshen", 2) * MODUS
            el = d - (p["north"].get("jinshen", 3) if p["north"] else 0) * MODUS \
                  - (p["south"].get("jinshen", 2) if p["south"] else 0) * MODUS
            boxes.append(_wing_eastwest(-(w / 2 - ed / 2), el, ed, zc, p["west"]))

        # 垂花门（院落分隔 gate）：放在本院北/南边缘
        if p["c"].get("enclosure", {}).get("northGate"):
            boxes.append(_gate(zc + d / 2, w))
        if p["c"].get("enclosure", {}).get("southGate"):
            boxes.append(_gate(zc - d / 2, w))

        z += p["d"] + gap
    return boxes


def _wing(cx, w, depth, zc, role_obj):
    """南北向屋翼：长边沿 X（面阔），厚沿 Z（进深）"""
    role = role_obj.get("role")
    return {
        "x": round(cx, 3), "y": WING_HEIGHT / 2, "z": round(zc, 3),
        "w": round(w, 3), "h": WING_HEIGHT, "d": round(depth, 3),
        "role": role, "label": label_of(role),
        "color": ROLE_COLORS.get(role, 0x999999),
    }


def _wing_eastwest(cx, el, ed, zc, role_obj):
    """东西厢：长边沿 Z（面阔），厚沿 X（进深）"""
    role = role_obj.get("role")
    return {
        "x": round(cx, 3), "y": WING_HEIGHT / 2, "z": round(zc, 3),
        "w": round(ed, 3), "h": WING_HEIGHT, "d": round(el, 3),
        "role": role, "label": label_of(role),
        "color": ROLE_COLORS.get(role, 0x999999),
    }


def _gate(zc, w):
    """垂花门：窄门洞示意（占位）"""
    return {
        "x": 0, "y": WING_HEIGHT / 2, "z": round(zc, 3),
        "w": round(min(w * 0.25, 4.0), 3), "h": WING_HEIGHT, "d": 1.0,
        "role": "chuihuamen", "label": label_of("chuihuamen"),
        "color": ROLE_COLORS.get("chuihuamen", 0x82A33A),
    }


# ---------------- ⑤ 体素 BOX 出口（本 MVP 即 box 清单本身） ----------------
def instance_to_boxes(instance):
    """实例图谱 -> 体素 BOX 清单。"""
    return compute_layout(instance)
