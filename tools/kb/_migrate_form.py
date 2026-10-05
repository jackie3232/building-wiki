#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性迁移：给 dict.json 的「空间角色 / 构件」补 form（形体原型）+ color（图示色）。

为什么要做：④⑤ 里原本硬编着角色名（"zhaimen"/"chuihuamen"/"houmen"/"youlang"/"yingbi"/
"yuanqiang"/"taiji"）与一张 ROLE_COLORS 角色色表——违反架构总纲 §7 判据 1「引擎零风格硬编」。
本脚本把这些事实搬进知识包（dict 词条），④⑤ 改为按声明执行。

做法：**文本级插入**（不重排 JSON），只在每个词条开括号后插两行，保持原有缩进与行内数组风格。
用法：python tools/kb/_migrate_form.py --dry-run | --write
"""
import argparse
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PACK = os.path.join(ROOT, "packs", "siheyuan")
DICT = os.path.join(PACK, "dict.json")

# role -> (form, color 或 None)
FORM = {
    # —— 房屋：房间原型（台基/地 + 顶 + 四壁，朝院一侧留门洞）——
    "zhengfang":    ({"kind": "room"}, "#C0504D"),
    "xiangfang":    ({"kind": "room"}, "#E0A030"),
    "daozuofang":   ({"kind": "room"}, "#4F81BD"),
    "houzhaofang":  ({"kind": "room"}, "#9B59B6"),
    "erfang":       ({"kind": "room"}, "#9B59B6"),
    # —— 门：门道原型（南北贯通房间 ± 门楼）；at = 落在墙环哪端 ——
    "chuihuamen":   ({"kind": "gate-passage", "at": "center",   "tower": True},  "#82A33A"),
    "zhaimen":      ({"kind": "gate-passage", "at": "east-end", "tower": True},  "#8B4513"),
    "houmen":       ({"kind": "gate-passage", "at": "west-end", "tower": False}, "#999999"),
    # —— 附属 ——
    "youlang":      ({"kind": "colonnade"},   "#808080"),
    "yingbi":       ({"kind": "screen-wall"}, "#B0A040"),
    # —— 墙：环形墙体（几何语义：独立院墙 vs 建筑墙，供 _resolve_boundary 判优先级）——
    "yuanqiang":    ({"kind": "ring-wall"}, "#7F7F7F"),
    "weiqiang":     ({"kind": "ring-wall"}, None),
    "kaziqiang":    ({"kind": "ring-wall"}, None),
    "houyanqiang":  ({"kind": "ring-wall"}, None),
    "buqiang":      ({"kind": "ring-wall"}, None),
    # —— 非实体的词：声明用途，不产构件 ——
    "chuantang":    ({"kind": "passage"}, None),
    "jiaodao":      ({"kind": "passage"}, None),
    "tingyuan":     ({"kind": "void"},    "#CFCFCF"),
    # —— 构件：台基是 ④ 为「声明了 norms.<role>.taiming 的房间」生成的底部构件 ——
    "taiji":        ({"kind": "base"}, "#9E9284"),
}

CATS = ["空间角色", "构件"]


def block_span(text, cat):
    """定位 top-level 类目 `  "<cat>": {` 的正文区间 [start, end)。"""
    m = re.search(r'^  "%s": \{\n' % re.escape(cat), text, re.M)
    if not m:
        raise SystemExit("找不到类目 %s" % cat)
    start = m.end()
    nxt = re.search(r'^  "[^"]+": ', text[start:], re.M)
    if not nxt:
        nxt = re.search(r'^  "__source_of_truth__"', text[start:], re.M)
    end = start + (nxt.start() if nxt else len(text) - start)
    return start, end


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = io.open(DICT, encoding="utf-8").read()
    before = json.loads(text)
    out = text
    added = 0
    for cat in CATS:
        s, e = block_span(out, cat)
        seg = out[s:e]
        for key, (form, color) in FORM.items():
            if key not in before.get(cat, {}):
                continue
            if "form" in before[cat][key]:
                continue
            pat = '    "%s": {\n' % re.escape(key)
            m = re.search(pat, seg)
            if not m:
                continue
            lines = "      \"form\": %s,\n" % json.dumps(form, ensure_ascii=False)
            if color:
                lines += "      \"color\": \"%s\",\n" % color
            seg = seg[:m.end()] + lines + seg[m.end():]
            added += 1
        out = out[:s] + seg + out[e:]

    after = json.loads(out)
    # 结构核验：除 form/color 外，其余必须逐字节等价
    drift = []
    for cat in before:
        if not isinstance(before[cat], dict):
            continue
        for k, v in before[cat].items():
            nv = after.get(cat, {}).get(k)
            if nv is None:
                drift.append("%s.%s 丢失" % (cat, k)); continue
            if not isinstance(v, dict):
                if nv != v:
                    drift.append("%s.%s 变了" % (cat, k))
                continue
            for kk, vv in v.items():
                if nv.get(kk) != vv:
                    drift.append("%s.%s.%s 变了" % (cat, k, kk))
        for k in after.get(cat, {}):
            if k not in before[cat]:
                drift.append("%s.%s 新增词条" % (cat, k))
    print("插入 form/color 的词条数：%d" % added)
    print("除 form/color 外的漂移：%s" % (drift or "无"))

    if args.write:
        if drift:
            raise SystemExit("拒绝写入：存在非预期漂移")
        io.open(DICT, "w", encoding="utf-8", newline="").write(out)
        print("已写入 %s" % os.path.relpath(DICT, ROOT))
    else:
        print("（dry-run，未写盘）")


if __name__ == "__main__":
    main()
