#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地调试：实例 → ⑤ boxes.json（复用服务端引擎 ④⑤，与线上同源）。

供 web 查看器 ?local= 旁路消费，完全绕开云端 Agent / MCP / 云存储。
产出默认落到 gitignored 的 tools/preview/out/boxes/，不污染仓库。

    python tools/preview/gen_boxes.py --instance tools/kb/baseline/jin3.instance.json

查看器配合（仓库根目录起 http.server）：
    http://localhost:<port>/web/?local=/preview/out/boxes/jin3.boxes.json
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", required=True, help="实例图谱 JSON 路径")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "boxes"),
                    help="输出目录（默认 tools/preview/out/boxes，已 gitignore）")
    ap.add_argument("--name", default=None, help="输出文件名（默认取实例文件名）")
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import compute_geometry, geometry_to_boxes  # noqa: E402

    inst = json.load(io.open(args.instance, encoding="utf-8"))
    boxes = geometry_to_boxes(compute_geometry(inst), instance=inst)

    os.makedirs(args.out, exist_ok=True)
    name = args.name or os.path.splitext(os.path.basename(args.instance))[0]
    path = os.path.join(args.out, name + ".boxes.json")
    json.dump(boxes, io.open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print("%s  (%d 体素)" % (os.path.relpath(path, ROOT), len(boxes)))


if __name__ == "__main__":
    main()
