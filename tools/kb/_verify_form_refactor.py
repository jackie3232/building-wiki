#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""form-driven 重构的**等价性验证**：老公式 vs 新实现，逐构件集合比对。

背景：④ 的重构（角色名硬编 → 知识包声明驱动）只有 jin1 一例有改动前的真实产物可比
（tools/preview/out/，2026-09-28 22:49）。jin2/3/4 覆盖的三条路径——垂花门居中开洞、
后门落在西端、明间穿堂——没有历史产物，故此处以**复刻原公式**的方式补证：

    本文件里的 `old_*` 全部是重构前 geometry.py 的原文逻辑（原样抄写，未做等价改写），
    只把已改名的知识键对齐（eastMargin/westMargin → margin、layout.xiangfang → wing），
    因为键名搬家不属"几何语义"。
    `compute_geometry_old` 复刻重构前的顶层分派 + 老助手，primitive（_geo_room/_geo_slab/
    _geo_front_wall/_geo_gate_tower/_geo_wall）直接复用现役实现——它们本轮未改语义。

判据：同一 instance 下，`old` 与现役 `compute_geometry` 的构件清单**顺序无关集合相等**。
用法：python tools/kb/_verify_form_refactor.py
"""
import glob
import io
import json
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "server"))
import engine.geometry as E  # noqa: E402

CASES = ["jin1", "jin2", "jin3", "jin4", "jin3-houmen"]


# ─────────────────────── 重构前原文（逐字抄写） ───────────────────────
def old_layout(instance):
    data = instance.get("data", instance)
    applied = instance.get("appliedRules", {})
    norms = applied.get("norms", {}) or {}
    modus = float(E._norms_get(norms, ("modus",), "模数"))
    courtyards = sorted(data.get("courtyards", []), key=lambda c: c.get("sequence", 0))
    plotted = []
    for c in courtyards:
        enc = c.get("enclosure", {})
        bei, nan, dong, xi = enc.get("bei"), enc.get("nan"), enc.get("dong"), enc.get("xi")
        ref = bei or nan or {}
        w = E._dim(ref, "miankuo", 5) * modus
        nd = E._dim(bei, "jinshen", 0) * modus
        sd = E._dim(nan, "jinshen", 0) * modus
        cdr = norms.get("courtDepthRatio", 0.6)
        if isinstance(cdr, dict):
            role = c.get("role")
            cdr_map = cdr.get("byRole", {})
            ratio = cdr_map.get(role, cdr.get("default", 0.6)) if role in cdr_map else cdr.get("default", 0.6)
        else:
            ratio = cdr
        court_depth = w * ratio
        d = nd + court_depth + sd
        plotted.append({"w": w, "d": d, "nd": nd, "sd": sd, "bei": bei, "nan": nan,
                        "dong": dong, "xi": xi, "c": c})
    total = sum(p["d"] for p in plotted)
    z = -total / 2
    for p in plotted:
        p["zc"] = z + p["d"] / 2
        z += p["d"]
    return plotted, norms, modus


def old_wing(cx, w, depth, zc, role_obj, open_side, norms):
    role = role_obj.get("role")
    return E._geo_room(role, cx, zc, w, E._role_height(norms, role, role_obj), depth,
                       open_side, norms, role_obj)


def old_daozuo(cx, w, sd, zc, role_obj, norms, has_gate):
    if not has_gate:
        return old_wing(cx, w, sd, zc, role_obj, "N", norms)
    role = role_obj.get("role")
    room_h = E._role_height(norms, role, role_obj)
    gs = round(float(E._norms_get(norms, ("zhaimen", "gateSpan"), "大门门道面阔")), 3)
    gh = round(float(E._norms_get(norms, ("zhaimen", "height"), "大门门楼高")), 3)
    margin = float(E._norms_get(norms, ("zhaimen", "margin"), "大门东侧与院墙留白"))
    gs = round(min(gs, w - 0.6), 3)
    gate_center = round(cx + (w / 2 - gs / 2 - margin), 3)
    seg_right = gate_center - gs / 2
    x_main = round((-w / 2 + seg_right) / 2, 3)
    w_main = round(seg_right + w / 2, 3)
    comps = []
    comps.extend(E._geo_room(role, x_main, zc, w_main, room_h, sd, "N", norms, role_obj))
    comps.extend(E._geo_room("zhaimen", gate_center, zc, gs, room_h, sd, ["S", "N"], norms))
    comps.extend(E._geo_gate_tower("zhaimen", gate_center, zc, gs, room_h, gh, sd, norms))
    return comps


def old_back_gate(cx, w, depth, zc, role_obj, gate_role, norms):
    role = role_obj.get("role")
    room_h = E._role_height(norms, role, role_obj)
    gs = round(float(E._norms_get(norms, ("houmen", "gateSpan"), "后门门道面阔")), 3)
    margin = float(E._norms_get(norms, ("houmen", "margin"), "后门西侧与院墙留白"))
    gs = round(min(gs, w - 0.6), 3)
    gate_center = round(cx - (w / 2 - gs / 2 - margin), 3)
    seg_left = gate_center + gs / 2
    x_main = round((seg_left + w / 2) / 2, 3)
    w_main = round(w / 2 - seg_left, 3)
    comps = []
    comps.extend(E._geo_room(role, x_main, zc, w_main, room_h, depth, "S", norms, role_obj))
    comps.extend(E._geo_room(gate_role, gate_center, zc, gs, room_h, depth, ["S", "N"], norms))
    return comps


def old_dongxi(cx, el, ed, zc, role_obj, norms):
    role = role_obj.get("role")
    open_side = "W" if cx > 0 else "E"
    return E._geo_room(role, cx, zc, ed, E._role_height(norms, role, role_obj), el,
                       open_side, norms, role_obj)


def old_xiangfang_length(role_obj, norms, d, nd, sd, modus):
    layout = E._norms_get(norms, ("layout", "wing"), "厢房布局约束（lengthMode/aisle/zAlign）")
    aisle = float(layout.get("aisle", 0))
    own = float(E._dim(role_obj, "miankuo", 0)) * modus
    court_net = d - nd - sd
    return round(min(own, court_net - 2 * aisle), 3)


def old_zhengfang_chuantang(cx, w, depth, zc, role_obj, norms):
    role = role_obj.get("role", "zhengfang")
    H = E._role_height(norms, role, role_obj)
    miankuo = E._dim(role_obj, "miankuo", 5)
    bay = (w / miankuo) if miankuo else w
    central = min(bay, w * 0.4)
    side = (w - central) / 2
    comps = []
    if side > 0.2:
        comps.extend(E._geo_room(role, cx - (central / 2 + side / 2), zc, side, H, depth, "S", norms, role_obj))
        comps.extend(E._geo_room(role, cx + (central / 2 + side / 2), zc, side, H, depth, "S", norms, role_obj))
    comps.extend(E._geo_room(role, cx, zc, central, H, depth, ["S", "N"], norms, role_obj))
    return comps


def old_chuihua(zc, w, role, norms):
    gs = round(float(E._norms_get(norms, ("chuihuamen", "gateSpan"), "垂花门面阔")), 3)
    gh = round(float(E._norms_get(norms, ("chuihuamen", "height"), "垂花门楼高")), 3)
    depth = float(E._norms_get(norms, ("chuihuamen", "depth"), "垂花门道进深"))
    base_h = float(E._norms_get(norms, ("room", "heightDefault"), "门道基准高"))
    comps = E._geo_room(role, 0, zc, gs, base_h, depth, ["S", "N"], norms)
    if gh > base_h + 0.05:
        comps.extend(E._geo_gate_tower(role, 0, zc, gs, base_h, gh, depth, norms))
    return comps


def old_wall_ring(c, w, zc, d, norms, draw_south=True, wall_kinds=None, ring_kinds=None):
    ring = c.get("ring", {}) or {}
    t = float(E._norms_get(norms, ("room", "thickness"), "墙面线偏移基准（取房间墙厚）"))

    def side_h_t(side):
        kind = (ring.get(side) or {}).get("kind")
        spec = (wall_kinds or {}).get(kind) if (kind and kind in (ring_kinds or set())) else None
        if not isinstance(spec, dict):
            spec = {}
        h, th = spec.get("height"), spec.get("thickness")
        H = float(h) if h is not None else float(E._norms_get(norms, ("wall", "height"), "院墙高"))
        T = float(th) if th is not None else float(E._norms_get(norms, ("wall", "thickness"), "院墙厚"))
        return H, T
    half = w / 2 - t / 2
    zN = zc + d / 2 - t / 2
    zS = zc - d / 2 + t / 2
    out = []

    def ns_wall(zc_wall, gate, side):
        H, T = side_h_t(side)
        if gate == "zhaimen":
            gs = float(E._norms_get(norms, ("zhaimen", "gateSpan"), "大门门道面阔"))
            gx = round(w / 2 - gs / 2 - float(E._norms_get(norms, ("zhaimen", "margin"), "大门东侧留白")), 3)
            gh = gs / 2
            l_seg = (gx - gh) - (-half)
            if l_seg > 0.01:
                out.append(E._geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (gx + gh)
            if r_seg > 0.01:
                out.append(E._geo_wall((gx + gh) + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        elif gate == "chuihuamen":
            gs = float(E._norms_get(norms, ("chuihuamen", "gateSpan"), "垂花门面阔"))
            gh = gs / 2
            l_seg = (0 - gh) - (-half)
            if l_seg > 0.01:
                out.append(E._geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (0 + gh)
            if r_seg > 0.01:
                out.append(E._geo_wall(gh + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        elif gate == "houmen":
            gs = float(E._norms_get(norms, ("houmen", "gateSpan"), "后门门道面阔"))
            gx = round(-(w / 2 - gs / 2 - float(E._norms_get(norms, ("houmen", "margin"), "后门西侧留白"))), 3)
            gh = gs / 2
            l_seg = (gx - gh) - (-half)
            if l_seg > 0.01:
                out.append(E._geo_wall(-half + l_seg / 2, zc_wall, l_seg, H, T, "yuanqiang"))
            r_seg = half - (gx + gh)
            if r_seg > 0.01:
                out.append(E._geo_wall((gx + gh) + r_seg / 2, zc_wall, r_seg, H, T, "yuanqiang"))
        else:
            out.append(E._geo_wall(0, zc_wall, w, H, T, "yuanqiang"))

    ns_wall(zN, (ring.get("bei") or {}).get("gate"), "bei")
    if draw_south:
        ns_wall(zS, (ring.get("nan") or {}).get("gate"), "nan")
    Hd, Td = side_h_t("dong")
    out.append(E._geo_wall(half, zc, Td, Hd, d - t, "yuanqiang"))
    Hx, Tx = side_h_t("xi")
    out.append(E._geo_wall(-half, zc, Tx, Hx, d - t, "yuanqiang"))
    return out


def compute_geometry_old(instance):
    plotted, norms, modus = old_layout(instance)
    _wall = (instance.get("appliedRules") or {}).get("wall") or {}
    wall_kinds = _wall.get("kinds") or {}
    ring_kinds = set(((_wall.get("taxonomy") or {}).get("围墙") or {}).get("kinds") or [])
    geometry = []
    for idx, p in enumerate(plotted):
        zc, w, d, nd, sd = p["zc"], p["w"], p["d"], p["nd"], p["sd"]
        if p["bei"]:
            nrole = p["bei"]
            ngate = ((nrole or {}).get("gate") or {}).get("role")
            if ngate:
                geometry.extend(old_back_gate(0, w, nd, zc + d / 2 - nd / 2, nrole, ngate, norms))
            elif (nrole or {}).get("chuantang"):
                geometry.extend(old_zhengfang_chuantang(0, w, nd, zc + d / 2 - nd / 2, nrole, norms))
            else:
                geometry.extend(old_wing(0, w, nd, zc + d / 2 - nd / 2, nrole, "S", norms))
        if p["nan"]:
            has_gate = bool((p["nan"] or {}).get("gate"))
            geometry.extend(old_daozuo(0, w, sd, zc - d / 2 + sd / 2, p["nan"], norms, has_gate))
        ew_z = zc + (sd - nd) / 2
        if p["dong"]:
            ed = E._dim(p["dong"], "jinshen", 0) * modus
            el = old_xiangfang_length(p["dong"], norms, d, nd, sd, modus)
            geometry.extend(old_dongxi(+(w / 2 - ed / 2), el, ed, ew_z, p["dong"], norms))
        if p["xi"]:
            ed = E._dim(p["xi"], "jinshen", 0) * modus
            el = old_xiangfang_length(p["xi"], norms, d, nd, sd, modus)
            geometry.extend(old_dongxi(-(w / 2 - ed / 2), el, ed, ew_z, p["xi"], norms))
        enc = p["c"].get("enclosure", {})
        if enc.get("beimen"):
            geometry.extend(old_chuihua(zc + d / 2, w, E._gate_role(enc["beimen"], "enclosure.beimen"), norms))
        if enc.get("nanmen"):
            geometry.extend(old_chuihua(zc - d / 2, w, E._gate_role(enc["nanmen"], "enclosure.nanmen"), norms))
        for per in (p["c"].get("peripheral") or []):
            if not isinstance(per, dict):
                continue
            prole = per.get("role")
            if prole == "youlang":
                pass                                   # 重构前亦不产生体素（各进未声明）
            elif prole == "yingbi":
                cfg = E._norms_get(norms, ("peripheral", "yingbi"), "影壁尺寸")
                bw, H, thick = float(cfg["width"]), float(cfg["height"]), float(cfg["depth"])
                zpos = zc - d / 2 + sd + float(cfg["zOffset"])
                geometry.append({"role": "yingbi",
                                 "center": {"x": round(w / 2 - bw / 2 - float(cfg["xInset"]), 3),
                                            "y": H / 2, "z": round(zpos, 3)},
                                 "size": {"w": bw, "h": H, "d": thick}})
        if p["c"].get("perimeter"):
            geometry.extend(old_wall_ring(p["c"], w, zc, d, norms, draw_south=(idx == 0),
                                          wall_kinds=wall_kinds, ring_kinds=ring_kinds))
    return E._resolve_boundary(geometry, norms, "yuanqiang")


# ───────────────────────────── 比对 ─────────────────────────────
def comp_key(g):
    c, s = g.get("center", {}), g.get("size", {})
    return json.dumps({"role": g.get("role"),
                       "c": [c.get("x"), c.get("y"), c.get("z")],
                       "s": [s.get("w"), s.get("h"), s.get("d")]}, sort_keys=True)


def main():
    asm = glob.glob(os.path.join(ROOT, "functions", "*", "skills",
                                 "traditional-building", "assemble.mjs"))[0]
    bad = 0
    for name in CASES:
        sk = io.open(os.path.join(ROOT, "tools/kb/baseline/%s.skeleton.json" % name),
                     encoding="utf-8").read()
        p = subprocess.run(["node", asm], input=sk, cwd=os.path.dirname(asm),
                           capture_output=True, text=True, encoding="utf-8")
        inst = json.loads(p.stdout)
        new = E.compute_geometry(inst)
        old = compute_geometry_old(inst)
        a, b = Counter(comp_key(g) for g in old), Counter(comp_key(g) for g in new)
        ok = (a == b)
        bad += 0 if ok else 1
        print("%-12s 老 %d · 新 %d · 集合相等=%s" % (name, len(old), len(new), ok))
        for s, lab in ((a - b, "仅老"), (b - a, "仅新")):
            for k, n in list(s.items())[:3]:
                print("     %s ×%d %s" % (lab, n, k[:200]))
    print()
    print("结论：%s" % ("重构语义等价（老公式与新实现逐构件一致）" if bad == 0
                        else "有 %d 个用例不等价" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
