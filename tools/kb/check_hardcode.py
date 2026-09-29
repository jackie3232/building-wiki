#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""总纲 §7 判据 1 的机器判据：**引擎零风格硬编**。

    python tools/kb/check_hardcode.py                    # 扫全部受检文件
    python tools/kb/check_hardcode.py --show-schema      # 连 schema 词一并列出（自检用）

判据原文：不出现任何**具体建筑类型 / 角色名 / 进数 / 拓扑字面量**。

口径（必须明确，否则这项检查会变成「靠感觉」）：
  · 命中对象 = 代码里的**字符串字面量**（含模板串）。注释与文档不算（它们允许举例）。
  · **schema 词不算硬编**：四至名(bei/nan/dong/xi…)、骨架声明字段名(gate/chuantang/miankuo…)、
    图谱分节名(meta/data/norms/occupancy/wall…)、dict 类目名(空间角色/构件/等级…)——
    这些是所有风格共用的**框架契约**，换成另一种建筑类型也不变。
  · **dict 词条的 key 才算风格事实**：角色名(zhengfang…)、墙种(kaziqiang…)、
    用途(guoting…)、材质/等级/构件… 出现在代码字面量里即违规。

为什么值得机器化：这类硬编不会报错、只会让「换一份知识包」失效——
它是架构判据，不是代码风格偏好，必须有可重复的检查，而不是靠人记。
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 受检文件：不变件（框架 / 引擎）。知识包与文档不在其列——它们**就是**风格事实的容器。
TARGETS = [
    "server/engine/geometry.py",
    "functions/agt-building-8gp5in9y2e59d69c/skills/traditional-building/assemble.mjs",
]

# schema 词白名单（框架契约，非风格事实）。与任何一份 pack 的内容无关。
SCHEMA = {
    # 图谱 / 文件分节
    "meta", "data", "desc", "label", "role", "style", "type", "dict", "ref",
    "appliedRules", "appliedType", "appliedDict", "zeroCoord", "generatedBy",
    "norms", "paramRanges", "occupancy", "position", "usage", "sequence",
    "orientation", "wall", "rules", "naming", "fallback", "kinds", "taxonomy",
    "provider", "kind", "center", "ring", "perimeter", "peripheral", "enclosure",
    "sides", "gate", "beimen", "nanmen", "relation", "thru", "via", "mount",
    "court", "when", "at", "step", "range", "default", "byRole", "rng",
    # 四至（拓扑槽位名，非角色名）
    "bei", "nan", "dong", "xi",
    # 骨架声明字段 / 业务量槽位
    "chuantang", "miankuo", "jinshen", "jin", "sequence_",
    # dict 类目名
    "空间角色", "院落", "构件", "方位", "材质", "等级", "用途", "关系",
    "开间", "尺度模数", "建筑类型",
}
# 代码里的比较/记号字符串（单字符侧标记等）
NOISE = {"N", "S", "E", "W", "V", "H", "ringBase", "buildingPart"}

STR_RE = re.compile(r"""(["'`])((?:\\.|(?!\1).)*)\1""")


def strip_comments(src, is_js):
    """去掉注释与 Python docstring —— 注释里允许举例说明。"""
    if is_js:
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        return "\n".join(re.sub(r"//.*$", "", ln) for ln in src.splitlines())
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(re.sub(r"#.*$", "", ln) for ln in src.splitlines())


def dict_keys():
    """本仓库所有 pack 里出现过的 dict 词条 key（= 风格事实的全集）。"""
    keys = {}
    base = os.path.join(ROOT, "functions")
    for fn in os.listdir(base):
        p = os.path.join(base, fn, "skills", "traditional-building", "packs")
        if not os.path.isdir(p):
            continue
        for style in os.listdir(p):
            dj = os.path.join(p, style, "dict.json")
            if not os.path.exists(dj):
                continue
            doc = json.load(io.open(dj, encoding="utf-8"))
            for cat, items in doc.items():
                if cat.startswith("_") or not isinstance(items, dict):
                    continue
                for k, v in items.items():
                    if isinstance(v, dict):
                        keys.setdefault(k, cat)
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-schema", action="store_true",
                    help="把落在 schema 白名单里的命中也列出来（自检判据本身）")
    ap.add_argument("--targets", default=None,
                    help="逗号分隔的受检文件（相对仓库根）；默认扫 TARGETS。用于证伪自检。")
    args = ap.parse_args()

    targets = args.targets.split(",") if args.targets else TARGETS
    style_keys = dict_keys()
    total_bad = 0
    for rel in targets:
        path = os.path.join(ROOT, rel)
        src = io.open(path, encoding="utf-8").read()
        code = strip_comments(src, rel.endswith(".mjs"))
        bad, schema_hits = [], []
        for i, line in enumerate(code.splitlines(), 1):
            for m in STR_RE.finditer(line):
                lit = m.group(2)
                if lit in NOISE:
                    continue
                if lit in SCHEMA:
                    schema_hits.append((i, lit))
                    continue
                if lit in style_keys:
                    bad.append((i, lit, style_keys[lit], line.strip()[:96]))
        print("=" * 72)
        print("%s：风格事实字面量 %d 处" % (rel, len(bad)))
        for i, lit, cat, ln in bad:
            print("  ✗ L%-5d 「%s」(%s)  | %s" % (i, lit, cat, ln))
        if args.show_schema:
            print("  (schema 白名单命中 %d 处：%s)"
                  % (len(schema_hits), ", ".join(sorted({l for _, l in schema_hits}))))
        total_bad += len(bad)

    print("=" * 72)
    print("结论：%s" % ("引擎零风格硬编 ✅（判据 1 满足）" if total_bad == 0
                       else "仍有 %d 处风格事实硬编 ❌" % total_bad))
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
