#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""墙角缺角诊断：墙盒子投影 XZ 栅格化，flood fill 从外部灌入空白，
未被灌到的封闭小空腔 = 墙角缺角（门洞/院子因连通外部被排除）。"""
import io
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "server"))
import engine.geometry as G  # noqa: E402

INST = os.path.join(ROOT, "tools/kb/baseline/jin3.instance.json")
inst = json.load(io.open(INST, encoding="utf-8"))
resolved = G.compute_geometry(inst)

thin = float(G._norms_get(inst.get("appliedRules", {}).get("norms", {}) or {},
                        ("room", "thickness"), "x") if False else 0.45)  # 占位，下面重取
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
        continue
    cx, cz = c["center"]["x"], c["center"]["z"]
    rects.append((cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2, c.get("role")))

res = 0.05
xs = [r[0] for r in rects] + [r[1] for r in rects]
zs = [r[2] for r in rects] + [r[3] for r in rects]
xmin, xmax = min(xs) - 1.0, max(xs) + 1.0
zmin, zmax = min(zs) - 1.0, max(zs) + 1.0
nx = int((xmax - xmin) / res) + 1
nz = int((zmax - zmin) / res) + 1
print("栅格 %dx%d  res=%.2f  墙盒子数=%d" % (nx, nz, res, len(rects)))

cov = [[0] * nx for _ in range(nz)]
for (x0, x1, z0, z1, role) in rects:
    i0, i1 = int((x0 - xmin) / res), int((x1 - xmin) / res)
    j0, j1 = int((z0 - zmin) / res), int((z1 - zmin) / res)
    for j in range(max(0, j0), min(nz, j1 + 1)):
        row = cov[j]
        for i in range(max(0, i0), min(nx, i1 + 1)):
            row[i] = 1

# flood fill 空白：从边界空白格灌入
visited = [[0] * nx for _ in range(nz)]
q = deque()
for i in range(nx):
    for j in (0, nz - 1):
        if not cov[j][i] and not visited[j][i]:
            visited[j][i] = 1
            q.append((i, j))
for j in range(nz):
    for i in (0, nx - 1):
        if not cov[j][i] and not visited[j][i]:
            visited[j][i] = 1
            q.append((i, j))
while q:
    i, j = q.popleft()
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ni, nj = i + di, j + dj
        if 0 <= ni < nx and 0 <= nj < nz and not cov[nj][ni] and not visited[nj][ni]:
            visited[nj][ni] = 1
            q.append((ni, nj))

# 收集封闭空腔（未访问的空白）连通块
seen = [[0] * nx for _ in range(nz)]
clusters = []
for j in range(nz):
    for i in range(nx):
        if not cov[j][i] and not visited[j][i] and not seen[j][i]:
            # BFS 该块
            q.append((i, j))
            seen[j][i] = 1
            cells = []
            while q:
                ci, cj = q.popleft()
                cells.append((ci, cj))
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ni, nj = ci + di, cj + dj
                    if 0 <= ni < nx and 0 <= nj < nz and not cov[nj][ni] \
                            and not visited[nj][ni] and not seen[nj][ni]:
                        seen[nj][ni] = 1
                        q.append((ni, nj))
            if len(cells) < 200:   # 仅报小空腔（院子等大块排除）
                ix = [c[0] for c in cells]
                jz = [c[1] for c in cells]
                bx0 = xmin + min(ix) * res
                bx1 = xmin + (max(ix) + 1) * res
                bz0 = zmin + min(jz) * res
                bz1 = zmin + (max(jz) + 1) * res
                clusters.append((round((bx0 + bx1) / 2, 2), round((bz0 + bz1) / 2, 2),
                                round(bx1 - bx0, 2), round(bz1 - bz0, 2), len(cells)))
print("\n封闭小空腔（墙角缺角）候选：")
for c in sorted(clusters, key=lambda x: -x[4]):
    print("  中心(%.2f,%.2f)  尺寸 %.2fx%.2f  格数=%d" % c)
if not clusters:
    print("  无（墙角无缺角）")
