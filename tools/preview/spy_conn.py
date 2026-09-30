#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2D 连通性复核：把所有墙盒子投影到 XZ 矩形，逐侧(东西南北)检查外圈是否连续。"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "server"))
import engine.geometry as G  # noqa: E402

INST = os.path.join(ROOT, "tools/kb/baseline/jin3.instance.json")
inst = json.load(io.open(INST, encoding="utf-8"))

_capt = {}


def _spy(components, norms, wall_role):
    _capt["norms"] = norms
    return components


G._resolve_boundary = _spy
resolved = G.compute_geometry(inst)
norms = _capt["norms"]

thin = float(G._norms_get(norms, ("room", "thickness"), "x")) + 0.15
rects = []
for c in resolved:
    s = c.get("size", {})
    w, h, d = s.get("w", 0), s.get("h", 0), s.get("d", 0)
    if min(w, d) > thin:
        continue  # 非墙
    cx, cz = c["center"]["x"], c["center"]["z"]
    rects.append((round(cx - w / 2, 3), round(cx + w / 2, 3),
                  round(cz - d / 2, 3), round(cz + d / 2, 3), c.get("role")))

xs = [r[0] for r in rects] + [r[1] for r in rects]
zs = [r[2] for r in rects] + [r[3] for r in rects]
xmin, xmax = min(xs), max(xs)
zmin, zmax = min(zs), max(zs)
print("墙体 X 范围 %.2f..%.2f  Z 范围 %.2f..%.2f" % (xmin, xmax, zmin, zmax))


def band_gaps(lo, hi, axis):
    """axis='x': 取 x∈[lo,hi] 的矩形，合并其 z 区间；axis='z': 取 z∈[lo,hi] 的矩形合并 x 区间。"""
    segs = []
    for (x0, x1, z0, z1, role) in rects:
        if axis == "x" and x1 > lo and x0 < hi:
            segs.append((z0, z1))
        elif axis == "z" and z1 > lo and z0 < hi:
            segs.append((x0, x1))
    segs = sorted(segs)
    merged = []
    for a, b in segs:
        if merged and a <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    # 全范围
    full = (zmin, zmax) if axis == "x" else (xmin, xmax)
    gaps = []
    cursor = full[0]
    for a, b in merged:
        if a - cursor > 0.2:
            gaps.append((round(cursor, 3), round(a, 3), round(a - cursor, 3)))
        cursor = max(cursor, b)
    if full[1] - cursor > 0.2:
        gaps.append((round(cursor, 3), round(full[1], 3), round(full[1] - cursor, 3)))
    return merged, gaps


for name, (lo, hi, axis, label) in {
    "东外墙": (xmax - 0.6, xmax + 0.1, "x", "东"),
    "西外墙": (xmin - 0.1, xmin + 0.6, "x", "西"),
    "北外墙": (zmax - 0.6, zmax + 0.1, "z", "北"),
    "南外墙": (zmin - 0.1, zmin + 0.6, "z", "南"),
}.items():
    merged, gaps = band_gaps(lo, hi, axis)
    print("\n%s (%s)  合并区间=%s" % (name, label, merged))
    if gaps:
        print("  >>> 真缺口: %s" % gaps)
    else:
        print("  OK 连续无缺口")
