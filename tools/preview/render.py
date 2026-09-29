#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离线渲染：⑤ 体素（boxes）→ PNG。零浏览器依赖。

为什么不用无头浏览器：本机跑 headless chrome 渲 WebGL 需 swiftshader 软件光栅，
实测两次都超时（>90s）且产出全白。静态图改用纯 Python 投影片 → 结果可复核。

    python tools/preview/render.py --instance tools/kb/baseline/jin3.instance.json \\
                                  --out tools/preview/out --name jin3

投影片：
  iso   等轴测（相机在 +x/+y/+z 方向），盒子画 3 个可见面（顶 / +x / +z），
        画家算法按 x+y+z 升序（远→近）。
  plan  俯视平面（x 向右、z 向下），按 y 升序画顶面 → 得「屋顶平面图」。
"""
import argparse
import io
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

C30 = math.cos(math.radians(30))
S30 = 0.5

# 可见面明暗（顶最亮，+x 次之，+z 最暗）——只做明暗，不改色相，
# 保证与前端 role 色块图例同色，不引入第二套"材料色"。
SHADE_TOP = 1.00
SHADE_X = 0.72
SHADE_Z = 0.50

BG = (247, 247, 248)
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"


def load_font(size):
    for p in (FONT_PATH, "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def rgb(c):
    if isinstance(c, str):
        c = int(c, 16) if c.startswith("0x") else int(c)
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def shade(col, k):
    return tuple(max(0, min(255, int(v * k))) for v in col)


def boxes_from_instance(inst):
    """instance（dict 或路径）→ ⑤ 体素（复用服务端引擎，保证与线上同源）。"""
    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import compute_geometry, geometry_to_boxes  # noqa: E402
    if isinstance(inst, str):
        inst = json.load(io.open(inst, encoding="utf-8"))
    return geometry_to_boxes(compute_geometry(inst), instance=inst)


def boxes_from_json(path):
    return json.load(io.open(path, encoding="utf-8"))


def proj3(x, y, z):
    """单点等轴测投影（image_y 向下，故 +y 在屏幕上朝上）。"""
    return ((x - z) * C30, (x + z) * S30 - y)


def project(b):
    """盒子 8 角的等轴测投影。"""
    x0, y0, z0 = b["x"], b["y"], b["z"]
    x1, y1, z1 = x0 + b["w"], y0 + b["h"], z0 + b["d"]
    return [proj3(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def render_iso(boxes, W=1760, H=1180, ss=2, pad=40):
    W2, H2 = W * ss, H * ss
    proj = [project(b) for b in boxes]
    minx = min(p[0] for pts in proj for p in pts)
    maxx = max(p[0] for pts in proj for p in pts)
    miny = min(p[1] for pts in proj for p in pts)
    maxy = max(p[1] for pts in proj for p in pts)
    spanx, spany = max(maxx - minx, 1e-6), max(maxy - miny, 1e-6)
    s = min((W2 - 2 * pad * ss) / spanx, (H2 - 2 * pad * ss) / spany)
    ox = W2 / 2 - (minx + maxx) / 2 * s
    oy = H2 / 2 - (miny + maxy) / 2 * s

    def px(p):
        sx, sy = proj3(p[0], p[1], p[2])
        return (ox + sx * s, oy + sy * s)

    img = Image.new("RGB", (W2, H2), BG)
    d = ImageDraw.Draw(img)

    # 远 → 近：位移越大（x+y+z）越靠近相机
    order = sorted(range(len(boxes)), key=lambda i: boxes[i]["x"] + boxes[i]["y"] + boxes[i]["z"])
    for i in order:
        b = boxes[i]
        x0, y0, z0 = b["x"], b["y"], b["z"]
        x1, y1, z1 = x0 + b["w"], y0 + b["h"], z0 + b["d"]
        base = rgb(b.get("color", 0x999999))
        f_top = [px(p) for p in ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))]
        f_x = [px(p) for p in ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
        f_z = [px(p) for p in ((x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1))]
        for poly, k in ((f_z, SHADE_Z), (f_x, SHADE_X), (f_top, SHADE_TOP)):
            c = shade(base, k)
            d.polygon(poly, fill=c, outline=c)
    return img.resize((W, H), Image.LANCZOS)


def role_table(boxes):
    tab, seen = [], set()
    for b in boxes:
        r = b.get("role")
        if r in seen:
            continue
        seen.add(r)
        n = sum(1 for o in boxes if o.get("role") == r)
        lab = next((o.get("label", r) for o in boxes if o.get("role") == r), r)
        tab.append((r, lab, rgb(b.get("color", 0x999999)), n))
    tab.sort(key=lambda t: -t[3])
    return tab


def cluster_2d(boxes, gap=0.35):
    """按 (x,z) 平面邻近聚类（网格哈希 + 并查集）。
    东西厢房在 x 上分开 → 各自成簇、各自标注；院墙成环 → 一簇（靠"质心在不在实体内"滤掉）。"""
    n = len(boxes)
    if n == 0:
        return []
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    cell = 2.0
    grid = {}
    for i, b in enumerate(boxes):
        for cx in range(int((b["x"] - gap) // cell), int((b["x"] + b["w"] + gap) // cell) + 1):
            for cz in range(int((b["z"] - gap) // cell), int((b["z"] + b["d"] + gap) // cell) + 1):
                grid.setdefault((cx, cz), []).append(i)
    for idxs in grid.values():
        for a in range(len(idxs)):
            for c in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[c]
                A, B = boxes[i], boxes[j]
                if (A["x"] - gap < B["x"] + B["w"] and B["x"] - gap < A["x"] + A["w"]
                        and A["z"] - gap < B["z"] + B["d"] and B["z"] - gap < A["z"] + A["d"]):
                    union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(boxes[i])
    return list(groups.values())


def cover_hash(boxes, cell=2.0):
    """网格哈希：格子 → 该格内所有盒子（供"某点被谁盖住"查询）。"""
    g = {}
    for b in boxes:
        for cx in range(int(b["x"] // cell), int((b["x"] + b["w"]) // cell) + 1):
            for cz in range(int(b["z"] // cell), int((b["z"] + b["d"]) // cell) + 1):
                g.setdefault((cx, cz), []).append(b)
    return g


def top_at(g, x, z, cell=2.0, role=None, not_role=None):
    """点 (x,z) 处最高面的 y。role 限定只看某 role，not_role 排除某 role。
    返回 None 表示此处无（符合条件的）实体。"""
    best = None
    for b in g.get((int(x // cell), int(z // cell)), ()):
        if role is not None and b["role"] != role:
            continue
        if not_role is not None and b["role"] == not_role:
            continue
        if b["x"] - 1e-6 <= x <= b["x"] + b["w"] + 1e-6 and \
           b["z"] - 1e-6 <= z <= b["z"] + b["d"] + 1e-6:
            t = b["y"] + b["h"]
            best = t if best is None else max(best, t)
    return best


def label_of(dict_doc, key, dflt=None):
    """dict 全类目查 key 的中文名（与引擎同一口径：不内置词表）。"""
    for cat, v in (dict_doc or {}).items():
        if cat.startswith("_") or cat == "meta":
            continue
        if isinstance(v, dict) and isinstance(v.get(key), dict):
            return v[key].get("label", key)
    return dflt if dflt is not None else key


def courtyard_layout(instance):
    """取 ④ 的 _layout —— 每院占地 w/d 与南北中心 zc（与几何计算同源，不另算）。"""
    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import _layout  # noqa: E402
    plotted, _norms, _modus = _layout(instance)
    return plotted


def render_plan(boxes, W=1400, H=1500, pad=64, legend=True, labels=True,
                courts=None, dict_doc=None):
    """俯视：x→右（东），−z→上（北）。按 y 升序画顶面，得屋顶平面图。"""
    xs = [b["x"] for b in boxes] + [b["x"] + b["w"] for b in boxes]
    zs = [b["z"] for b in boxes] + [b["z"] + b["d"] for b in boxes]
    minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
    spanx, spanz = max(maxx - minx, 1e-6), max(maxz - minz, 1e-6)
    s = min((W - 2 * pad) / spanx, (H - 2 * pad) / spanz)
    ox = W / 2 - (minx + maxx) / 2 * s
    oy = H / 2 + (minz + maxz) / 2 * s  # image_y = -z（北朝上）

    def X(x):
        return ox + x * s

    def Y(z):
        return oy - z * s

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for b in sorted(boxes, key=lambda o: o["y"]):
        c = rgb(b.get("color", 0x999999))
        d.rectangle([X(b["x"]), Y(b["z"] + b["d"]), X(b["x"] + b["w"]), Y(b["z"])],
                    fill=c, outline=c)

    placed = []          # 已占位文本框，防叠字

    def put(txt, x, y, fnt, fg, bg=None, stroke=None):
        w = d.textlength(txt, font=fnt)
        h = getattr(fnt, "size", 20) + 6
        box = (x - w / 2 - 6, y - h / 2, x + w / 2 + 6, y + h / 2)
        for o in placed:
            if not (box[2] < o[0] or box[0] > o[2] or box[3] < o[1] or box[1] > o[3]):
                return False
        if bg:
            d.rectangle(box, fill=bg)
            d.text((x, y), txt, font=fnt, fill=fg, anchor="mm")
        else:
            d.text((x, y), txt, font=fnt, fill=fg, anchor="mm",
                   stroke_width=3, stroke_fill=stroke or (255, 255, 255))
        placed.append(box)
        return True

    # 院角色（外院/内院/厅房院/后罩院）——首要标注，先占位
    if courts:
        fc = load_font(24)
        for p in courts:
            role = (p.get("c") or {}).get("role")
            x0, x1 = X(-p["w"] / 2), X(p["w"] / 2)
            z_s, z_n = p["zc"] - p["d"] / 2, p["zc"] + p["d"] / 2
            o_s, o_n = z_s + p["sd"], z_n - p["nd"]    # 露天院落 = 去掉南北房进深
            d.rectangle([x0, Y(o_n), x1, Y(o_s)], outline=(150, 150, 158))
            put(label_of(dict_doc, role, role), (x0 + x1) / 2, Y((o_s + o_n) / 2),
                fc, (255, 255, 255), bg=(88, 88, 98))

    if labels:
        f = load_font(21)
        g = cover_hash(boxes)
        for role in sorted({b["role"] for b in boxes}):
            bs = [o for o in boxes if o["role"] == role]
            lab = next((o.get("label", role) for o in bs), role)
            for cl in cluster_2d(bs):
                if len(cl) < 12:
                    continue
                cx = sum(o["x"] + o["w"] / 2 for o in cl) / len(cl)
                cz = sum(o["z"] + o["d"] / 2 for o in cl) / len(cl)
                # 只在「质心落在本簇实体内、且本簇面没被别的 role 压住」时才标
                inside = any(o["x"] <= cx <= o["x"] + o["w"] and
                             o["z"] <= cz <= o["z"] + o["d"] for o in cl)
                if not inside:
                    continue
                top_self = top_at(g, cx, cz, role=role)
                top_other = top_at(g, cx, cz, not_role=role)
                if top_self is None:
                    continue
                if top_other is not None and top_other > top_self + 1e-6:
                    continue
                put(lab, X(cx), Y(cz), f, (28, 28, 32))

    # 指北针（右上）
    nx, ny = W - 66, 56
    d.polygon([(nx, ny), (nx - 13, ny + 34), (nx, ny + 24), (nx + 13, ny + 34)],
              fill=(40, 40, 45))
    d.text((nx, ny + 46), "北", font=load_font(22), fill=(40, 40, 45), anchor="mm")

    # 比例尺（左下）
    bar = 5.0 * s
    bx, by = 40, H - 44
    d.line([(bx, by), (bx + bar, by)], fill=(60, 60, 65), width=3)
    d.line([(bx, by - 7), (bx, by + 7)], fill=(60, 60, 65), width=3)
    d.line([(bx + bar, by - 7), (bx + bar, by + 7)], fill=(60, 60, 65), width=3)
    d.text((bx, by - 24), "5 m", font=load_font(19), fill=(60, 60, 65))

    if legend:
        f = load_font(20)
        tab = role_table(boxes)
        lh = 30
        lx, ly = 16, 16
        lw = int(max(d.textlength("%s (%s) %d" % (t[1], t[0], t[3]), font=f) for t in tab)) + 46
        lh_tot = lh * len(tab) + 16
        d.rectangle([lx, ly, lx + lw, ly + lh_tot], fill=(255, 255, 255),
                    outline=(200, 200, 205))
        for j, (r, lab, col, n) in enumerate(tab):
            yy = ly + 8 + j * lh
            d.rectangle([lx + 12, yy + 3, lx + 32, yy + 23], fill=col,
                        outline=(120, 120, 120))
            d.text((lx + 40, yy), "%s (%s) %d" % (lab, r, n), fill=(40, 40, 45), font=f)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", help="instance JSON 路径（内部跑 ④⑤）")
    ap.add_argument("--boxes", help="boxes JSON 路径（直接用）")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--name", default=None, help="输出文件前缀，默认取输入文件名")
    ap.add_argument("--views", default="iso,plan")
    ap.add_argument("--width", type=int, default=1760)
    ap.add_argument("--height", type=int, default=1180)
    args = ap.parse_args()

    if not args.instance and not args.boxes:
        sys.exit("须给 --instance 或 --boxes")
    name = args.name or os.path.splitext(os.path.basename(args.instance or args.boxes))[0]
    name = name.replace(".instance", "").replace(".boxes", "")
    inst = None
    if args.boxes:
        boxes = boxes_from_json(args.boxes)
    else:
        inst = json.load(io.open(args.instance, encoding="utf-8"))
        boxes = boxes_from_instance(inst)
    os.makedirs(args.out, exist_ok=True)

    made = []
    if "iso" in args.views:
        p = os.path.join(args.out, "render-%s-iso.png" % name)
        render_iso(boxes, args.width, args.height).save(p)
        made.append(p)
    if "plan" in args.views:
        p = os.path.join(args.out, "render-%s-plan.png" % name)
        render_plan(boxes, courts=courtyard_layout(inst) if inst else None,
                    dict_doc=(inst or {}).get("appliedDict")).save(p)
        made.append(p)
    for p in made:
        print("%s  (%d 体素, %d KB)" % (os.path.relpath(p, ROOT), len(boxes),
                                        os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
