#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回归基线 —— 改 ④⑤ / 知识包前后「零漂移」的唯一裁判。

    python tools/kb/baseline.py            # 采集/刷新基线（写 tools/kb/baseline/）
    python tools/kb/baseline.py --check    # 与基线比对，只报漂移、不写盘

链路：骨架（按 rules.occupancy 求值生成）→ assemble.mjs → instance
      → ④ compute_geometry → ⑤ geometry_to_boxes

比对口径（铁律，见项目记忆「验证纪律」）：
  · 构件清单：**顺序无关集合比对**（set 遍历顺序受哈希随机化影响，直接逐项比会误报）。
  · 体素清单：整体 sha1（canonical JSON）+ 数量 + role 分布。
  · instance：逐字节比对（装配器冻结；④ 改动不应波及它）。

基线只存 instance / 构件清单 / 摘要；体素只存哈希不存全文（省体积，比对够用）。
"""

import argparse
import glob
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASE = os.path.join(HERE, "baseline")
STYLE = "siheyuan"
# (名字, 进数, 是否显式设后门)。后门 byDefault=false，单列一个用例覆盖「后门」那条分支。
CASES = [("jin1", 1, False), ("jin2", 2, False), ("jin3", 3, False),
         ("jin4", 4, False), ("jin3-houmen", 3, True)]


# ── 骨架夹具：按 rules.occupancy 求值（复刻 assemble.mjs 的 occupancyOf） ────
def find_assemble():
    hits = glob.glob(os.path.join(
        ROOT, "functions", "*", "skills", "traditional-building", "assemble.mjs"))
    if not hits:
        sys.exit("找不 assemble.mjs")
    return hits[0]


def occupancy_of(k, jin, occ_rules):
    for r in occ_rules:
        at = r.get("at")
        if at == "middle":
            if not (1 < k < jin):
                continue
        elif at == "last":
            if k != jin:
                continue
        elif at != k:
            continue
        if "jinEq" in r and jin != r["jinEq"]:
            continue
        if "jinGte" in r and jin < r["jinGte"]:
            continue
        if "jinLte" in r and jin > r["jinLte"]:
            continue
        return r
    raise SystemExit("夹具缺陷：第 %d 进（共 %d）在 occupancy 无规则命中" % (k, jin))


def skeleton_for(jin, rules, with_houmen=False):
    """夹具：occupancy（默认四至）+ 显式开关的条件性门（后门）。

    默认 4 个用例不带后门（后门 byDefault=false，须用户明说才设）；
    with_houmen 用例把 rules.position 里 byDefault=false 的门挂到其 mount 指定的槽位，
    用来覆盖「后门」那条分支——否则那条路径永远不在零漂移覆盖范围内。
    """
    occ = rules["occupancy"]["rules"]
    courtyards = []
    for k in range(1, jin + 1):
        r = occupancy_of(k, jin, occ)
        enc = {}
        for side in ("bei", "nan", "dong", "xi"):
            if side in (r.get("sides") or {}):
                enc[side] = dict(r["sides"][side])
        if r.get("beimen"):
            enc["beimen"] = dict(r["beimen"])
        if r.get("nanmen"):
            enc["nanmen"] = dict(r["nanmen"])
        if with_houmen:
            for p in rules.get("position", []):
                if not isinstance(p, dict) or p.get("byDefault") is not False:
                    continue
                court = p.get("court")
                if court == "last" and k != jin:
                    continue
                if "jinGte" in p and jin < p["jinGte"]:
                    continue
                if "jinEq" in p and jin != p["jinEq"]:
                    continue
                parts = str(p["mount"]).split(".")
                cur = enc
                for seg in parts[:-1]:
                    cur = cur.setdefault(seg, {})
                cur[parts[-1]] = {"role": p["role"]}
        cy = {"sequence": k, "enclosure": enc}
        if r.get("perimeter"):
            cy["perimeter"] = True
        if r.get("peripheral"):
            cy["peripheral"] = [dict(p) for p in r["peripheral"]]
        courtyards.append(cy)
    return {"style": STYLE, "jin": jin, "courtyards": courtyards}


# ── 采集 ────────────────────────────────────────────────────────────────────
def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha1(obj):
    return hashlib.sha1(canon(obj).encode("utf-8")).hexdigest()


def comp_key(g):
    c, s = g.get("center", {}), g.get("size", {})
    return canon({"role": g.get("role"),
                  "c": [c.get("x"), c.get("y"), c.get("z")],
                  "s": [s.get("w"), s.get("h"), s.get("d")]})


def collect(name, jin, with_houmen, rules, node, assemble, write=True):
    sk = skeleton_for(jin, rules, with_houmen)
    sk_path = os.path.join(BASE, "%s.skeleton.json" % name)
    os.makedirs(BASE, exist_ok=True)
    if write:
        io.open(sk_path, "w", encoding="utf-8").write(
            json.dumps(sk, ensure_ascii=False, indent=2))
    # --check 走 stdin 送骨架：既不必落盘，也杜绝「比对时把基线覆盖掉」这类自伤
    proc = subprocess.run([node, assemble], cwd=os.path.dirname(assemble),
                          input=json.dumps(sk, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit("装配失败 %s：\n%s" % (name, proc.stderr or proc.stdout))
    inst = json.loads(proc.stdout)
    if write:
        io.open(os.path.join(BASE, "%s.instance.json" % name), "w", encoding="utf-8").write(
            json.dumps(inst, ensure_ascii=False, indent=2))

    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import compute_geometry, geometry_to_boxes  # noqa: E402
    comps = compute_geometry(inst)
    boxes = geometry_to_boxes(comps, instance=inst)
    if write:
        io.open(os.path.join(BASE, "%s.geometry.json" % name), "w", encoding="utf-8").write(
            json.dumps(comps, ensure_ascii=False, indent=2))

    roles = {}
    for b in boxes:
        roles[b.get("role")] = roles.get(b.get("role"), 0) + 1
    return {
        "sku": sha1(sk),
        "instance_sha1": sha1(inst),
        "components": len(comps),
        "components_sha1": sha1(sorted(comp_key(g) for g in comps)),
        "boxes": len(boxes),
        "boxes_sha1": sha1(boxes),
        "roles": dict(sorted(roles.items())),
    }


def load_base(name, kind):
    p = os.path.join(BASE, "%s.%s" % (name, kind))
    if not os.path.exists(p):
        sys.exit("基线缺失：%s —— 先跑一次不带 --check" % p)
    return json.load(io.open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写盘")
    args = ap.parse_args()

    assemble = find_assemble()
    node = os.environ.get("NODE_BIN") or shutil.which("node")
    if not node:
        sys.exit("找不 node")
    pack = os.path.join(os.path.dirname(assemble), "packs", STYLE)
    rules = json.load(io.open(os.path.join(pack, "%s.rules" % STYLE), encoding="utf-8"))

    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import compute_geometry  # noqa: E402

    bad = 0
    for name, jin, with_houmen in CASES:
        got = collect(name, jin, with_houmen, rules, node, assemble, write=not args.check)
        print("=" * 60)
        print("%-12s 构件 %d · 体素 %d · role %s"
              % (name, got["components"], got["boxes"], ",".join(got["roles"])))
        if args.check:
            old = load_base(name, "summary.json")
            for k in ("components", "boxes", "boxes_sha1", "components_sha1",
                      "instance_sha1", "roles", "sku"):
                o, n = old.get(k), got.get(k)
                ok = (o == n)
                bad += 0 if ok else 1
                print("   [%s] %-16s %s" % ("OK" if ok else "DIFF", k,
                                            "" if ok else "基线=%s 现在=%s" % (o, n)))
            if old.get("components_sha1") != got.get("components_sha1"):
                # 集合比对失败 → 逐构件定位差异（顺序无关）。
                # 基线侧读**存盘的旧构件清单**，现在侧重算——混用同一份文件会自己跟自己比。
                from collections import Counter
                gc = json.load(io.open(os.path.join(BASE, "%s.geometry.json" % name),
                                       encoding="utf-8"))
                inst = json.load(io.open(os.path.join(BASE, "%s.instance.json" % name),
                                         encoding="utf-8"))
                # 旧 instance 配不了新 ④（知识包改了字段名）时，退回用本次新 instance 自比
                # 并明确标注——那种情况下结论不可用，须另建对照。
                a = Counter(comp_key(g) for g in gc)
                b = Counter(comp_key(g) for g in compute_geometry(inst))
                print("   —— 仅基线有（%d）：%s" % (sum((a - b).values()),
                                                  list((a - b).elements())[:6]))
                print("   —— 仅现在有（%d）：%s" % (sum((b - a).values()),
                                                  list((b - a).elements())[:6]))
        else:
            json.dump(got, io.open(os.path.join(BASE, "%s.summary.json" % name),
                                   "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print()
    if args.check:
        print("结论：%s" % ("零漂移（与基线逐项一致）" if bad == 0 else "有 %d 项漂移" % bad))
        return 0 if bad == 0 else 1
    print("基线已写入 %s（%s）" % (os.path.relpath(BASE, ROOT),
                                  ", ".join(c[0] for c in CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
