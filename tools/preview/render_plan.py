#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把体素 boxes 投影成 XZ 平面 ASCII 图，便于肉眼定位墙角缝隙。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOXES = os.path.join(ROOT, "tools/preview/out/boxes/jin3.instance.boxes.json")
boxes = json.load(open(BOXES, encoding="utf-8"))
walls = [b for b in boxes if b["h"] >= 0.45]  # 只留墙(薄板 h~0.3 排除)

res = 0.3
xs = []
zs = []
for b in walls:
    xs += [b["x"] - b["w"] / 2, b["x"] + b["w"] / 2]
    zs += [b["z"] - b["d"] / 2, b["z"] + b["d"] / 2]
xmin, xmax = min(xs) - 0.5, max(xs) + 0.5
zmin, zmax = min(zs) - 0.5, max(zs) + 0.5
nx = int((xmax - xmin) / res) + 1
nz = int((zmax - zmin) / res) + 1
rects = [(b["x"] - b["w"] / 2, b["x"] + b["w"] / 2, b["z"] - b["d"] / 2, b["z"] + b["d"] / 2) for b in walls]
grid = [["."] * nx for _ in range(nz)]
for j in range(nz):
    zc0, zc1 = zmin + j * res, zmin + (j + 1) * res
    for i in range(nx):
        xc0, xc1 = xmin + i * res, xmin + (i + 1) * res
        for (x0, x1, z0, z1) in rects:
            if xc0 < x1 and xc1 > x0 and zc0 < z1 and zc1 > z0:
                grid[j][i] = "#"
                break

# 北在上：行序反转
lines = ["".join(grid[j]) for j in range(nz - 1, -1, -1)]
out = "\n".join(lines)
open(os.path.join(ROOT, "tools/preview/plan.txt"), "w", encoding="utf-8").write(out)
print("plan %dx%d res=%.2f -> tools/preview/plan.txt" % (nx, nz, res))
print("列(x): %.1f..%.1f  行(z,顶=北): %.1f..%.1f" % (xmin, xmax, zmax, zmin))
