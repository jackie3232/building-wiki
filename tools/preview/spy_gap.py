#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复测围墙缝隙：抓 _resolve_boundary 前后状态，量化每个共线墙线。"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "server"))
import engine.geometry as G  # noqa: E402

captured = {}


def spy(components, norms, wall_role):
    captured["before"] = [dict(c) for c in components]
    captured["wall_role"] = wall_role
    captured["norms"] = norms
    return orig(components, norms, wall_role)


orig = G._resolve_boundary
G._resolve_boundary = spy

INST = os.path.join(ROOT, "tools/kb/baseline/jin3.instance.json")
inst = json.load(io.open(INST, encoding="utf-8"))
resolved = G.compute_geometry(inst)
before = captured["before"]
wr = captured["wall_role"]
norms = captured["norms"]

thin = float(G._norms_get(norms, ("room", "thickness"), "x")) + 0.15


def classify(c):
    s = c.get("size", {})
    w, h, d = s.get("w", 0), s.get("h", 0), s.get("d", 0)
    if min(w, d) > thin:
        return None
    if w < d:
        orient, line = "V", round(c["center"]["x"], 1)
        lo, hi = c["center"]["z"] - d / 2, c["center"]["z"] + d / 2
    else:
        orient, line = "H", round(c["center"]["z"], 1)
        lo, hi = c["center"]["x"] - w / 2, c["center"]["x"] + w / 2
    return orient, line, lo, hi


def collect(comps):
    by_line = {}
    for c in comps:
        cl = classify(c)
        if not cl:
            continue
        orient, line, lo, hi = cl
        role = c.get("role")
        by_line.setdefault((orient, line), []).append((round(lo, 3), round(hi, 3), role))
    return by_line


before_lines = collect(before)
after_lines = collect(resolved)

print("wall_role =", wr, " thin =", thin)
print("=" * 70)

# 只关心有院墙(yuanqiang)参与的墙线
all_lines = sorted(set(before_lines) | set(after_lines))
for key in all_lines:
    b = before_lines.get(key, [])
    a = after_lines.get(key, [])
    b_yuan = [iv for iv in b if iv[2] == wr]
    b_bld = [iv for iv in b if iv[2] != wr]
    a_yuan = [iv for iv in a if iv[2] == wr]
    a_bld = [iv for iv in a if iv[2] != wr]
    tag = ""
    if b_yuan and not a_yuan:
        tag = "  <<< 院墙整段被替换/删除"
    elif b_yuan and a_yuan:
        tag = "  (院墙保留/被切)"
    if b_yuan or a_yuan:
        print("%s line=%s  before: yuan=%s bld=%s | after: yuan=%s bld=%s%s"
              % (key[0], key[1], b_yuan, b_bld, a_yuan, a_bld, tag))

print("=" * 70)
# 测缺口：对每条线，合并【所有墙(院墙+建筑)】区间，看是否连续（允许门洞，但报 >0.2m 的断口）
for key in sorted(set(before_lines) | set(after_lines)):
    a = after_lines.get(key, [])
    if not a:
        continue
    # 合并院墙 + 建筑墙
    merged = G._merge_ivs([(iv[0], iv[1]) for iv in a])
    # 找 >0.2m 的断口
    gaps = []
    for i in range(1, len(merged)):
        g = merged[i][0] - merged[i - 1][1]
        if g > 0.2:
            gaps.append(round(g, 3))
    if gaps:
        print("GAP %s line=%s 合并区间=%s 断口=%s" % (key[0], key[1], merged, gaps))
