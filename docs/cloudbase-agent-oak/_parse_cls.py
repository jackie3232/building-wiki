#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时诊断工具：把 queryLogs 落盘的原始 JSON 抽成可读日志行。

用法:
    python _parse_cls.py <落盘文件> [--grep 关键字]

落盘文件是 MCP 工具返回的完整 JSON（可能前置若干说明文字）。
本脚本只读、不写任何业务文件。
"""
import json
import re
import sys


def load(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    i = raw.find("{")
    if i < 0:
        raise SystemExit("未找到 JSON 主体")
    return json.loads(raw[i:])


def rows_of(doc):
    res = (doc.get("data") or {}).get("results") or {}
    return res.get("Results") or res.get("results") or []


def content_of(row):
    c = row.get("Content", "")
    m = re.search(r'"__CONTENT__":"(.*?)","FileName"', c, re.S)
    return json.loads('"' + m.group(1) + '"') if m else c


def main():
    path = sys.argv[1]
    grep = None
    if "--grep" in sys.argv:
        grep = sys.argv[sys.argv.index("--grep") + 1]
    doc = load(path)
    rows = rows_of(doc)
    print("N=%d" % len(rows))
    seen = []
    for k, r in enumerate(rows):
        seen.append((r.get("Timestamp"), k, content_of(r)))
    seen.sort(key=lambda x: (x[0], x[1]))
    for ts, _, txt in seen:
        if grep and grep not in txt:
            continue
        print(ts, "|", txt)


if __name__ == "__main__":
    main()
