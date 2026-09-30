#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""围墙「吃墙」不变式回归测试（boundarySegmentRealization）。

锁死一条通用规则：沿每一条院落边界，
  - 有建筑处：独立院墙(yuanqiang) 被建筑墙吃掉 —— 二者不得显著重叠（双墙）；
  - 无建筑处：独立院墙完整保留 —— 院墙∪建筑墙 沿边界连续无洞（漏风）。
即用户原话「有建筑的时候，那一段的围墙就是被建筑吃掉的；没有建筑的时候，围墙是完整的」。

这条规则在 ④ 引擎层是几何驱动、与具体建筑类型/知识包无关的（见 geometry._resolve_boundary）：
院墙与建筑墙按「共线 0.1m + 区间相减」去重。本测试在 box 产物上校验该不变式，
覆盖所有 baseline，任何让吃墙失效的改动（如墙心对齐回归导致院墙贯穿建筑）都会让
重叠体积极速膨胀而 FAIL。

    # 全量 baseline
    python tools/preview/spy_wall_invariant.py
    # 单个实例
    python tools/preview/spy_wall_invariant.py --instance tools/kb/baseline/jin3.instance.json

退出码 0=全部通过，1=存在失败。
"""
import argparse
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 容差：当前各 baseline 院墙/建筑墙重叠体积极小(≈0.005~0.007 m³)，仅角部 0.3m 接缝残差。
# 放宽到 0.02 给 3× 余量；一旦吃墙失效（院墙贯穿建筑），重叠会到数百 m³ 量级，必 FAIL。
EPS_OVERLAP_M3 = 0.02
# 边界覆盖内部缺口 > 该值即判「漏风」（院墙该在处没补上）。
GAP_TOL_M = 0.10


def _vol(b):
    return (b["x"] - b["w"] / 2, b["x"] + b["w"] / 2,
            b["z"] - b["d"] / 2, b["z"] + b["d"] / 2,
            b["y"], b["y"] + b["h"])


def _ov3(a, b):
    A, B = _vol(a), _vol(b)
    ox = min(A[1], B[1]) - max(A[0], B[0])
    oz = min(A[3], B[3]) - max(A[2], B[2])
    oy = min(A[5], B[5]) - max(A[4], B[4])
    if ox <= 0 or oz <= 0 or oy <= 0:
        return 0.0
    return ox * oz * oy


def _merge_ivs(ivs):
    out = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def check_instance(inst):
    """返回 (ok, report_lines)。"""
    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import compute_geometry, geometry_to_boxes  # noqa: E402

    wall_role = ((inst.get("appliedRules") or {}).get("wall") or {}).get("ref")
    if not isinstance(wall_role, str) or not wall_role:
        return False, ["  图谱缺陷：appliedRules.wall.ref 缺失，无法识别独立院墙角色"]

    boxes = geometry_to_boxes(compute_geometry(inst), instance=inst)
    yq = [b for b in boxes if b.get("role") == wall_role]
    bl = [b for b in boxes if b.get("role") != wall_role and b["h"] >= 0.45]
    lines = []

    # (1) 吃墙：院墙 vs 建筑墙 3D 重叠体积
    tot = 0.0
    pairs = 0
    for y in yq:
        for b in bl:
            v = _ov3(y, b)
            if v > 1e-9:
                tot += v
                pairs += 1
    ok_overlap = tot <= EPS_OVERLAP_M3
    lines.append("  吃墙(无双墙): 重叠体积=%.4f m³ (%d 对)  上限=%.2f  -> %s"
                 % (tot, pairs, EPS_OVERLAP_M3, "PASS" if ok_overlap else "FAIL"))

    # (2) 无洞：只查【外圈 4 条边】的闭合性。院墙(ring)的核心语义是外圈围合连续，
    #     内部横隔墙(卡子墙/垂花门等)本就留中央门道，不算漏风。
    #     外圈 4 条边取「所有墙盒」的最外极值（非仅院墙，因北/南界常被建筑后檐墙包办）。
    #     占用判定用【全部 box】(含建筑楼板/屋顶本体, h<0.45)，否则建筑本体占满的边界会被误判漏风。
    wall_boxes = [b for b in boxes if b["h"] >= 0.45]   # 所有墙(含建筑墙)
    wx = [round(b["x"], 1) for b in wall_boxes if b["w"] < b["d"]]
    wz = [round(b["z"], 1) for b in wall_boxes if b["w"] >= b["d"]]
    if not wx or not wz:
        return False, ["  图谱缺陷：墙盒未形成可识别的外圈(缺少东西或南北向墙)"]
    bnd_lines = [("V", max(wx)), ("V", min(wx)), ("H", max(wz)), ("H", min(wz))]

    # 外圈外接矩形（全部 box 极值），用于把「靠边的全部盒」归到对应边
    all_ext = []
    for b in boxes:
        all_ext.append((b["x"] - b["w"] / 2, b["x"] + b["w"] / 2,
                       b["z"] - b["d"] / 2, b["z"] + b["d"] / 2))
    xmin = min(a for a, _, _, _ in all_ext)
    xmax = max(b for _, b, _, _ in all_ext)
    zmin = min(c for _, _, c, _ in all_ext)
    zmax = max(d for _, _, _, d in all_ext)

    worst_gap = 0.0
    boundary_lines = 0
    fail_lines = []
    TOL = 0.5  # 归边容差：抓取贴边墙盒与建筑本体盒
    for orient, line in bnd_lines:
        ivs = []
        for b in boxes:
            if orient == "V":
                if abs(b["x"] - line) > TOL:
                    continue
                lo, hi = b["z"] - b["d"] / 2, b["z"] + b["d"] / 2
            else:
                if abs(b["z"] - line) > TOL:
                    continue
                lo, hi = b["x"] - b["w"] / 2, b["x"] + b["w"] / 2
            ivs.append((lo, hi))
        if not ivs:
            continue
        boundary_lines += 1
        merged = _merge_ivs(ivs)
        for i in range(1, len(merged)):
            g = merged[i][0] - merged[i - 1][1]
            if g > worst_gap:
                worst_gap = g
            if g > GAP_TOL_M:
                fail_lines.append("    %s 外圈线 %.1f 缺口 %.2f m @[%.2f,%.2f]"
                                  % (orient, line, g, merged[i - 1][1], merged[i][0]))
    ok_cont = worst_gap <= GAP_TOL_M
    lines.append("  无洞(完整): 边界线=%d 条  最大内部缺口=%.3f m  上限=%.2f  -> %s"
                 % (boundary_lines, worst_gap, GAP_TOL_M, "PASS" if ok_cont else "FAIL"))
    for fl in fail_lines:
        lines.append(fl)

    ok = ok_overlap and ok_cont
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default=None, help="单个实例；缺省则跑全部 baseline")
    args = ap.parse_args()

    if args.instance:
        insts = [args.instance]
    else:
        insts = sorted(glob.glob(os.path.join(ROOT, "tools", "kb", "baseline", "*.instance.json")))

    all_ok = True
    for path in insts:
        try:
            inst = json.load(io.open(path, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print("[ERR] %s: %s" % (os.path.basename(path), e))
            all_ok = False
            continue
        ok, rep = check_instance(inst)
        tag = "PASS" if ok else "FAIL"
        print("[%s] %s" % (tag, os.path.basename(path)))
        for ln in rep:
            print(ln)
        if not ok:
            all_ok = False

    print("\n=> 围墙吃墙不变式:", "全部通过 ✅" if all_ok else "存在失败 ❌")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
