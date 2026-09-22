"""零漂移验证：Agent 原生装配器(assemble.mjs) vs 现 Python 装配器(assemble_instance)。

纪律（项目验证铁律）：改装配段后必须与改动前逐字段深比对。
这里比对的两端是**同一契约的两种实现**，故要求结构完全相等
（唯一豁免：meta.generatedBy —— 它本应反映真实来源，Python 写死的占位串不算事实）。

跑法：server/.venv/Scripts/python.exe docs/cloudbase-agent-oak/_verify_port.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = r"D:\sourcecodes\building.wiki"
SERVER = os.path.join(ROOT, "server")
SKILL = os.path.join(ROOT, "docs", "cloudbase-agent-oak", "skill", "skills", "siheyuan")
KNOWLEDGE = os.path.join(SERVER, "knowledge")
# 可选：第一个位置参数指定知识中心目录（用于验证打包后的 skill 自足）
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    KNOWLEDGE = os.path.abspath(sys.argv[1])
NODE = r"C:\Users\jackie\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"

sys.path.insert(0, SERVER)
from engine.geometry import build_instance, assemble_instance  # noqa: E402
from engine.understanding import skeleton_of  # noqa: E402


def normalize(o, path=""):
    """剔除 meta.generatedBy（实现署名，非事实）。"""
    if isinstance(o, dict):
        return {k: normalize(v, f"{path}.{k}") for k, v in o.items()
                if not (path == ".meta" and k == "generatedBy")}
    if isinstance(o, list):
        return [normalize(v, f"{path}[]") for v in o]
    return o


def diff(a, b, path="", out=None, limit=12):
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append(f"{path}: 类型 {type(a).__name__} != {type(b).__name__}")
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: JS 多出 {b[k]!r}")
            elif k not in b:
                out.append(f"{path}.{k}: Python 多出 {a[k]!r}")
            else:
                diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: 长度 {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {a!r} != {b!r}")
    return out


def main():
    print(f"knowledge = {KNOWLEDGE}")
    print(f"skill     = {SKILL}\n")
    # 测试域 = 知识中心声明的 jin 值域（paramRanges），不再硬编——域一改，测试范围随之。
    with open(os.path.join(KNOWLEDGE, "siheyuan.rules"), encoding="utf-8") as f:
        _rules = json.load(f)
    jin_lo, jin_hi = _rules["paramRanges"]["jin"]["range"]
    print(f"jin 值域 = {jin_lo}-{jin_hi}（来自 paramRanges）\n")
    all_ok = True
    for jin in range(jin_lo, jin_hi + 1):
        py_base = build_instance(jin)
        sk = skeleton_of(py_base["data"]["courtyards"])
        py = assemble_instance(sk)

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump(sk, f, ensure_ascii=False)
            tmp = f.name
        try:
            r = subprocess.run(
                [NODE, os.path.join(SKILL, "assemble.mjs"),
                 "--knowledge", KNOWLEDGE, "--skeleton", tmp],
                capture_output=True, text=True, encoding="utf-8", timeout=120)
        finally:
            os.unlink(tmp)

        if r.returncode != 0:
            print(f"jin={jin}: [FAIL] node 退出 {r.returncode}\n{r.stderr[:500]}")
            all_ok = False
            continue

        js = json.loads(r.stdout)
        d = diff(normalize(py), normalize(js))
        if d:
            all_ok = False
            print(f"jin={jin}: [DIFF] {len(d)} 处（最多列 12）")
            for line in d:
                print("   ", line)
        else:
            print(f"jin={jin}: [OK] 结构全等  "
                  f"(courtyards={len(js['data']['courtyards'])}, "
                  f"appliedDict={len(js.get('appliedDict', {}))} 类, "
                  f"norms={len(js['appliedRules']['norms'])} 前缀)")

    print("\n=== 结论:", "零漂移 ✅" if all_ok else "存在差异 ❌", "===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
