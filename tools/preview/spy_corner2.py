#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""墙角缺角诊断 v2：基于体素 boxes.json，在 XZ 栅格上检测 L 形内缺角
（空格的两相邻垂直方向都是墙 = 拐角缺方）。区别于门洞(左右两面墙,对立方向)。"""
import json
import os
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOXES = os.path.join(ROOT, "tools/preview/out/boxes/jin3.instance.boxes.json")
boxes = json.load(open(BOXES, encoding="utf-8"))

# 仅取墙状体素（楼板/屋顶 h~0.3 排除，只留 h>=0.45 的墙）
walls = [b for b in boxes if b["h"] >= 0.45]
print("墙状体素数:", len(walls), " / 总:", len(boxes))

res = 0.2
xs = [b["x"] for b in walls] + [b["x"] + b["w"] / 2 for b in walls] + [b["x"] - b["w"] / 2 for b in walls]
zs = [b["z"] for b in walls] + [b["z"] + b["d"] / 2 for b in walls] + [b["z"] - b["d"] / 2 for b in walls]
xmin, xmax = min(xs) - 1, max(xs) + 1
zmin, zmax = min(zs) - 1, max(zs) + 1
nx = int((xmax - xmin) / res) + 1
nz = int((zmax - zmin) / res) + 1
# 格边界与墙矩形相交即算覆盖（避免格心判定的边界量化噪声）
rects = [(b["x"] - b["w"] / 2, b["x"] + b["w"] / 2, b["z"] - b["d"] / 2, b["z"] + b["d"] / 2) for b in walls]
cov = [[0] * nx for _ in range(nz)]
for j in range(nz):
    zc0, zc1 = zmin + j * res, zmin + (j + 1) * res
    for i in range(nx):
        xc0, xc1 = xmin + i * res, xmin + (i + 1) * res
        hit = 0
        for (x0, x1, z0, z1) in rects:
            if xc0 < x1 and xc1 > x0 and zc0 < z1 and zc1 > z0:
                hit = 1
                break
        cov[j][i] = hit


def is_notch(cov, i, j, nx, nz):
    up = j > 0 and cov[j - 1][i]
    dn = j < nz - 1 and cov[j + 1][i]
    lf = i > 0 and cov[j][i - 1]
    rt = i < nx - 1 and cov[j][i + 1]
    # 两相邻垂直方向都是墙：上左/上右/下左/下右
    return (up and lf) or (up and rt) or (dn and lf) or (dn and rt)


seen = [[0] * nx for _ in range(nz)]
clusters = []
for j in range(nz):
    for i in range(nx):
        if cov[j][i] or seen[j][i]:
            continue
        if not is_notch(cov, i, j, nx, nz):
            continue
        q = deque([(i, j)])
        seen[j][i] = 1
        cells = []
        while q:
            ci, cj = q.popleft()
            cells.append((ci, cj))
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = ci + di, cj + dj
                if 0 <= ni < nx and 0 <= nj < nz and not cov[nj][ni] and not seen[nj][ni] \
                        and is_notch(cov, ni, nj, nx, nz):
                    seen[nj][ni] = 1
                    q.append((ni, nj))
        if 1 <= len(cells) <= 80:  # 仅小缺角(0.1~0.8m)
            ix = [c[0] for c in cells]
            jz = [c[1] for c in cells]
            cx = round(xmin + (min(ix) + max(ix) + 1) / 2 * res, 2)
            cz = round(zmin + (min(jz) + max(jz) + 1) / 2 * res, 2)
            ww = round((max(ix) - min(ix) + 1) * res, 2)
            hh = round((max(jz) - min(jz) + 1) * res, 2)
            clusters.append((cx, cz, ww, hh, len(cells), cells))

print("L 形内缺角候选：")
for c in sorted(clusters, key=lambda x: -x[4]):
    print("  中心(%.2f,%.2f) 尺寸 %.2fx%.2f 格=%d" % (c[0], c[1], c[2], c[3], c[4]))


# 打印第一个候选的局部 ASCII（确认是墙角缺角而非噪声）
def ascii_view(ci, cj, R=6):
    lines = []
    for dj in range(-R, R + 1):
        row = []
        for di in range(-R, R + 1):
            i, j = ci + di, cj + dj
            if 0 <= i < nx and 0 <= j < nz:
                row.append("#" if cov[j][i] else ".")
            else:
                row.append(" ")
        lines.append("".join(row))
    return "\n".join(lines)


if clusters:
    c = max(clusters, key=lambda x: x[4])
    # 用簇中心格
    ci = int((c[0] - xmin) / res)
    cj = int((c[1] - zmin) / res)
    print("\n局部 ASCII (中心 %.2f,%.2f, #=墙 .=空)：\n" % (c[0], c[1]))
    print(ascii_view(ci, cj, 7))
