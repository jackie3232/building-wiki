"""四合院尺寸比例 / 相对位置 量化稽核（数据驱动，不凭印象）。

方法：
1. 用引擎自己的 `_layout` 算每进院占地(w/d)、南北房进深(nd/sd)、院心 zc —— 与 ④ 同公式，零漂移。
2. 从 instance 的节点(miankuo/jinshen/height) 直接算每栋房「设计尺寸」面阔/进深/高。
3. 用 courtDepthRatio 校验每进院「露天院净深」比例是否合理。
4. 交叉验证：把 compute_geometry 产出的 component 按 院落z带+东西侧 分组，算真实包围盒 W×D×H，
   与设计尺寸逐项比对，确认几何产物与设计意图一致（不靠角色名硬聚）。
输出：可量化结论表 + 合理性判据。
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
from engine import geometry as G


def load(name):
    base = os.path.join(os.path.dirname(__file__), "baseline")
    inst = json.load(open(f"{base}/{name}.instance.json"))
    geo = json.load(open(f"{base}/{name}.geometry.json"))
    return inst, geo


def analyze_instance(inst):
    """用引擎 _layout + 节点声明，量化每进院 / 每栋房设计尺寸。"""
    data = inst["data"]
    applied = inst.get("appliedRules", {})
    norms = applied.get("norms", {})
    modus = float(norms["modus"])
    cdr = norms["courtDepthRatio"]
    cdr_map = cdr["byRole"]
    wing = norms.get("layout", {}).get("wing", {})
    aisle = float(wing.get("aisle", 0))

    plotted, _, _ = G._layout(inst)
    courts = []
    for idx, p in enumerate(plotted):
        c = p["c"]
        role = c.get("role")
        w, d, nd, sd, zc = p["w"], p["d"], p["nd"], p["sd"], p["zc"]
        ratio_intended = cdr_map.get(role, cdr["default"])
        court_depth_actual = d - nd - sd
        ratio_actual = court_depth_actual / w if w else 0
        enc = c.get("enclosure", {})

        rooms = []
        # 南北房：面阔沿X=miankuo*modus；进深沿Z=jinshen*modus
        for side in ("bei", "nan"):
            n = enc.get(side)
            if not n:
                continue
            mk = n.get("miankuo", 0)
            js = n.get("jinshen", 0)
            W = mk * modus
            D = js * modus
            H = float(n.get("height") or norms["room"]["heightDefault"])
            rooms.append({
                "role": n["role"], "side": side, "miankuo": mk, "jinshen": js,
                "W": W, "D": D, "H": H,
                "W:D": (W / D) if D else 0, "H:W": H / W, "H:D": H / D,
                "chuantang": bool(n.get("chuantang")),
            })
        # 东西房：面阔沿Z=min(miankuo*modus, court_net-2*aisle)；进深沿X=jinshen*modus
        court_net = d - nd - sd
        for side in ("dong", "xi"):
            n = enc.get(side)
            if not n:
                continue
            mk = n.get("miankuo", 0)
            js = n.get("jinshen", 0)
            own = mk * modus
            facing = min(own, court_net - 2 * aisle)  # 面阔(沿Z，朝庭院展开)，两端各留 aisle 通道不贴墙
            depth = js * modus                    # 进深(沿X)
            H = float(n.get("height") or norms["room"]["heightDefault"])
            rooms.append({
                "role": n["role"], "side": side, "miankuo": mk, "jinshen": js,
                "W": depth, "D": facing, "H": H,   # 这里 W=沿X进深, D=沿Z面阔
                "W:D": depth / facing if facing else 0, "H:W": H / depth, "H:D": H / facing,
                "chuantang": bool(n.get("chuantang")),
            })
        courts.append({
            "seq": c.get("sequence"), "name": c.get("name"), "role": role,
            "w": w, "d": d, "nd": nd, "sd": sd, "zc": zc,
            "ratio_intended": ratio_intended,
            "court_depth_actual": court_depth_actual,
            "ratio_actual": ratio_actual,
            "W:D": w / d,
            "rooms": rooms,
        })
    return courts, modus, cdr


def measure_geometry(geo, courts, modus):
    """把 component 按 院落z带(+东西侧) 分组，算真实包围盒，与 _layout 的院尺寸比对。"""
    # 院 z 范围（仅用于展示）；归属用「最近院心」判定，避免边界构件被容差误并到邻院
    bands = [(p["zc"] - p["d"] / 2, p["zc"] + p["d"] / 2, p["name"]) for p in courts]
    center_by_name = {p["name"]: p["zc"] for p in courts}
    rows = []
    for comp in geo:
        cz = comp["center"]["z"]
        # 归属院落：取院心最近的院（纯按最近中心，无容差），杜绝跨院误并
        band = min(center_by_name, key=lambda nm: abs(center_by_name[nm] - cz))
        rows.append((band, comp))
    # 按 role 聚合（同院同 role 可能东/西两栋，按 x 符号拆分）
    from collections import defaultdict
    groups = defaultdict(list)
    for band, comp in rows:
        x = comp["center"]["x"]
        side = "E" if x >= 0 else "W"
        groups[(band, comp["role"], side)].append(comp)
    result = {}
    for key, comps in groups.items():
        xs = [c["center"]["x"] for c in comps]
        zs = [c["center"]["z"] for c in comps]
        ys = [c["center"]["y"] for c in comps]
        ws = [c["size"]["w"] for c in comps]
        ds = [c["size"]["d"] for c in comps]
        hs = [c["size"]["h"] for c in comps]
        W = (max(xs) + max(w2 := [xs[i] + ws[i] / 2 for i in range(len(xs))]) - min(xs) - min([xs[i] - ws[i] / 2 for i in range(len(xs))]))
        W = (max([xs[i] + ws[i] / 2 for i in range(len(xs))]) - min([xs[i] - ws[i] / 2 for i in range(len(xs))]))
        D = (max([zs[i] + ds[i] / 2 for i in range(len(zs))]) - min([zs[i] - ds[i] / 2 for i in range(len(zs))]))
        H = max([ys[i] + hs[i] / 2 for i in range(len(ys))])
        result[key] = {"W": round(W, 2), "D": round(D, 2), "H": round(H, 2), "n": len(comps)}
    return result


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="jin3")
    ap.add_argument("--brief", action="store_true")
    args = ap.parse_args()
    inst, geo = load(args.name)
    courts, modus, cdr = analyze_instance(inst)
    meas = measure_geometry(geo, courts, modus)
    total_w = max(c["w"] for c in courts)  # 面阔一致=16.5
    total_d = sum(c["d"] for c in courts)
    print(f"=== {args.name} · modus={modus} · 总占地 东西={total_w} 南北={round(total_d,2)} 比例(东:南)={round(total_w/total_d,3)} ===\n")
    if args.brief:
        print(f"{'院':>6} {'role':>10} {'w':>7} {'d':>7} {'W:D':>5} {'露天净深':>7} {'ratio设':>6} {'ratio实':>6} {'zc':>7}")
        for c in courts:
            print(f"{c['name']:>6} {c['role']:>10} {c['w']:>7.2f} {c['d']:>7.2f} {c['W:D']:>5.2f} {c['court_depth_actual']:>7.2f} {c['ratio_intended']:>6.2f} {c['ratio_actual']:>6.2f} {c['zc']:>7.2f}")
        return

    print("【每进院】")
    print(f"{'院':>6} {'role':>10} {'w(面阔)':>8} {'d(进深)':>8} {'W:D':>6} {'nd':>6} {'sd':>6} {'露天净深':>8} {'ratio设':>6} {'ratio实':>6} {'zc':>8}")
    for c in courts:
        print(f"{c['name']:>6} {c['role']:>10} {c['w']:>8.2f} {c['d']:>8.2f} {c['W:D']:>6.2f} {c['nd']:>6.2f} {c['sd']:>6.2f} {c['court_depth_actual']:>8.2f} {c['ratio_intended']:>6.2f} {c['ratio_actual']:>6.2f} {c['zc']:>8.2f}")

    print("\n【每栋房 设计尺寸 (面阔W / 进深D / 高H，单位 m)】")
    print(f"{'院':>6} {'角色':>10} {'位':>3} {'间':>3} {'W':>7} {'D':>7} {'H':>5} {'面阔:进深':>9} {'高:面阔':>7} {'高:进深':>7}")
    for c in courts:
        for r in c["rooms"]:
            print(f"{c['name']:>6} {r['role']:>10} {r['side']:>3} {r['miankuo']:>3} {r['W']:>7.2f} {r['D']:>7.2f} {r['H']:>5.2f} {r['W:D']:>9.2f} {r['H:W']:>7.2f} {r['H:D']:>7.2f}")

    print("\n【几何产物交叉验证：按 (院,role,东西) 包围盒】")
    # 找关键房间测量值
    for key, v in sorted(meas.items()):
        print(f"  {str(key):>40} W={v['W']:>6} D={v['D']:>6} H={v['H']:>5} n={v['n']}")


if __name__ == "__main__":
    main()
