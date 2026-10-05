#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识包编译器：源词条(.md) -> 三件套片段。

    python tools/kb/compile.py            # 编译 + 与现有盘包比对 + 写 build/
    python tools/kb/compile.py --check    # 只比对，不写盘

语法规则见 docs/知识包源语法.md（本文档是它的可执行实现）。

源（人写）： packs/<style>/src/<key>.md      —— 一个对象一篇词条
产物（机器）：packs/<style>/build/<key>.json  —— 缓存，可随时重建
"""
import argparse
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# ── 路由表 = schema 的可执行形式：一个字段 = 一件，谁都不许跨 ──────────────
# 精确字段
EXACT = {
    "是什么": "dict.desc",
    "等级": "dict.level",
    "材质": "dict.material",
    "颜色": "dict.color",
    "可变量": "dict.modular",     # 逗号列表 -> 数组
    "组成": "dict.structs",       # 逗号列表 -> 数组
    "形体原型": "dict.form.kind",  # 原语名，见 §6
    "形体方位": "dict.form.at",    # 嵌在房屋上的门落在哪端（east-end / west-end / center）
    "形体门楼": "dict.form.tower",  # 门道间是否带门楼（bool）
    "形体说明": "norms.desc",
}
# 前缀字段（值内可继续用点路径表达嵌套）
PREFIX = {
    "结构": "type",        # 结构.*  -> type.*
    "形体参数": "norms",   # 形体参数.* -> norms.*
}
LIST_FIELDS = ("可变量", "组成")

TITLE_RE = re.compile(r"^##\s*(.+?)\s*\((\w+)\)\s*$", re.M)
LINE_RE = re.compile(r"^([^\s#][^：:]*)[：:]\s*(.*)$")
SEG_RE = re.compile(r"^([^\[\]]+)(?:\[(\d+)\])?$")


def find_skill():
    hits = glob.glob(os.path.join(ROOT, "functions", "*", "skills", "traditional-building"))
    if not hits:
        sys.exit("找不 traditional-building skill 目录")
    return hits[0]


def as_scalar(v):
    v = v.strip()
    if re.match(r"^-?\d+$", v):
        return int(v)
    if re.match(r"^-?\d+\.\d+$", v):
        return float(v)
    if v in ("true", "false"):
        return v == "true"
    return v


def as_list(v):
    return [as_scalar(s) for s in v.split(",") if s.strip()]


def set_path(root, path, value):
    """按点路径写入嵌套 dict/list。'a.b[0].c' -> root['a']['b'][0]['c']。"""
    parts = []
    for seg in path.split("."):
        m = SEG_RE.match(seg.strip())
        if not m:
            sys.exit("路径段非法：%r（期望 name 或 name[i]）" % seg)
        parts.append((m.group(1).strip(), int(m.group(2)) if m.group(2) else None))
    cur = root
    for i, (name, idx) in enumerate(parts):
        last = (i == len(parts) - 1)
        if idx is None:
            if last:
                if name in cur:
                    sys.exit("字段重复：%s" % path)
                cur[name] = value
            else:
                cur = cur.setdefault(name, {})
        else:
            lst = cur.setdefault(name, [])
            while len(lst) <= idx:
                lst.append({})
            if last:
                lst[idx] = value
            else:
                cur = lst[idx]


def parse_entry(path):
    txt = io.open(path, encoding="utf-8").read()
    m = TITLE_RE.search(txt)
    if not m:
        sys.exit("%s：缺 '## 中文名 (key)' 标题行" % os.path.basename(path))
    name, key = m.group(1).strip(), m.group(2)

    out = {"dict": {}, "type": {}, "norms": {}}
    touched = set()
    for lineno, line in enumerate(txt.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#") or line.startswith("##"):
            continue
        m2 = LINE_RE.match(line)
        if not m2:
            sys.exit("%s 第 %d 行：不是「字段：值」格式 -> %r" % (os.path.basename(path), lineno, line))
        field, raw = m2.group(1).strip(), m2.group(2)

        if field in EXACT:
            dst = EXACT[field]
            val = as_list(raw) if field in LIST_FIELDS else as_scalar(raw)
        else:
            head = field.split(".")[0]
            if head not in PREFIX:
                sys.exit("%s 第 %d 行：未知字段「%s」（合法：%s / %s.*）"
                         % (os.path.basename(path), lineno, field,
                            " ".join(EXACT), " ".join(PREFIX)))
            tail = field[len(head) + 1:] if "." in field else ""
            if not tail:
                sys.exit("%s 第 %d 行：「%s」必须写成「%s.路径」" % (os.path.basename(path), lineno, head, head))
            dst = PREFIX[head] + "." + tail
            val = as_scalar(raw)

        bucket, _, sub = dst.partition(".")
        touched.add(dst)
        set_path(out[bucket], sub, val)

    # dict 段只在「该词条写过 dict 字段」时才存在；label 由标题中文名兜底。
    # 反例：courtyard 只活在 type 里（dict 的「院落」类目装的是 tingyuan/waiyuan 等
    # 院落种类，不含 courtyard 本身），不该凭空产出一个 dict.label。
    if out["dict"]:
        out["dict"].setdefault("label", name)
    return key, name, out, touched


def dict_lookup(dict_all, key):
    """在 dict 全类目中查 key（空间角色 / 构件 / 材质 / 等级 …），而非写死 空间角色。"""
    hits = [(cat, v[key]) for cat, v in dict_all.items()
            if not cat.startswith("_") and cat != "meta"
            and isinstance(v, dict) and isinstance(v.get(key), dict)]
    if not hits:
        return {}
    if len(hits) > 1:
        print("   [WARN] dict 中 key=%s 命中多个类目：%s" % (key, [c for c, _ in hits]))
    return hits[0][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="siheyuan")
    ap.add_argument("--check", action="store_true", help="只比对，不写 build/")
    args = ap.parse_args()

    pack = os.path.join(ROOT, "packs", args.style)
    src_dir = os.path.join(pack, "src")
    if not os.path.isdir(src_dir):
        sys.exit("没有源目录：%s" % src_dir)

    real = {
        "dict": json.load(io.open(os.path.join(pack, "dict.json"), encoding="utf-8")),
        "type": json.load(io.open(os.path.join(pack, "siheyuan.type.json"), encoding="utf-8")),
        "rules": json.load(io.open(os.path.join(pack, "siheyuan.rules"), encoding="utf-8")),
    }
    build_dir = os.path.join(pack, "build")
    if not args.check:
        os.makedirs(build_dir, exist_ok=True)

    ok_all = True
    for path in sorted(glob.glob(os.path.join(src_dir, "*.md"))):
        key, name, out, touched = parse_entry(path)
        print("=" * 56)
        print("%s  →  %s (%s)" % (os.path.basename(path), name, key))

        ref = {}
        if any(t.startswith("dict.") for t in touched):
            ref["dict"] = dict_lookup(real["dict"], key)
        if any(t.startswith("type.") for t in touched):
            node = real["type"]
            for seg in key.split("."):
                node = node.get(seg, {})
            ref["type"] = node
        if any(t.startswith("norms.") for t in touched):
            ref["norms"] = real["rules"]["norms"].get(key, {})

        # 逐段比对：**dict 段含 form/color**（form 曾单独成桶、只当 [NEW] 打印，
        # 结果「源写 room、盘包是 gate-passage」这种错被藏住 —— 现一律并进 dict 逐字段比）。
        for b in ("dict", "type", "norms"):
            if not out[b]:
                continue
            g, r = out[b], ref.get(b) or {}
            for kk in sorted(set(list(g.keys()) + list(r.keys()))):
                gv, rv = g.get(kk, "<缺>"), r.get(kk, "<缺>")
                ok = (gv == rv)
                ok_all &= ok
                print("   [%s] %-6s %-12s %s" % ("OK" if ok else "DIFF", b, kk,
                                                 "" if ok else "源=%r 现有=%r" % (gv, rv)))

        if not args.check:
            io.open(os.path.join(build_dir, key + ".json"), "w", encoding="utf-8").write(
                json.dumps(out, ensure_ascii=False, indent=2))

    print()
    print("结论：%s" % ("零漂移（源可 1:1 还原现有三件套）" if ok_all else "有漂移，schema 需修"))
    if ok_all and not args.check:
        print("产物已写入 %s" % os.path.relpath(build_dir, ROOT))


if __name__ == "__main__":
    main()
