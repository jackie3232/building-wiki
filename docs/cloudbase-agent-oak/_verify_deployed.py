"""复核部署落地：下载线上代码包，检查 skills/ 与 agent.yaml 是否真进去（2026-09-22）。

用法：server/.venv/Scripts/python.exe docs/cloudbase-agent-oak/_verify_deployed.py <downloadUrl>
"""
import hashlib
import io
import os
import sys
import urllib.request
import zipfile

ROOT = r"D:\sourcecodes\building.wiki"
STAGED = r"C:\temp\bw-agent\agent-code"
OUT = os.path.join(ROOT, "docs", "cloudbase-agent-oak", "_deployed_check.txt")


def main():
    url = sys.argv[1]
    lines = []
    p = lines.append

    p("downloading ...")
    data = urllib.request.urlopen(url, timeout=600).read()
    p(f"bytes: {len(data)}  ({len(data)/1048576:.1f} MB)")
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    p(f"entries: {len(names)}")
    p("")

    p("=== skills/ 相关条目 ===")
    hit = [n for n in sorted(names) if "skills" in n.lower()]
    for n in hit:
        p("  " + n)
    if not hit:
        p("  (无 —— skills/ 没进包！)")
    p("")

    p("=== 顶层条目（排除 node_modules）===")
    for t in sorted(set(n.split("/")[0] for n in names)):
        if t.startswith("node_modules") or t.startswith("/"):
            continue
        p("  " + t)
    p("")

    p("=== 关键文件 vs 本地暂存（sha256 前 16 位）===")
    checks = [
        "agent.yaml",
        "skills/siheyuan/SKILL.md",
        "skills/siheyuan/assemble.mjs",
        "skills/siheyuan/knowledge/dict.json",
        "skills/siheyuan/knowledge/siheyuan.rules",
        "skills/siheyuan/knowledge/siheyuan.type.json",
    ]
    allok = True
    for name in checks:
        try:
            b = z.read(name)
            h = hashlib.sha256(b).hexdigest()
        except KeyError:
            p(f"  {name:46s} [线上缺失]")
            allok = False
            continue
        local = os.path.join(STAGED, name.replace("/", os.sep))
        if os.path.exists(local):
            lb = open(local, "rb").read()
            lh = hashlib.sha256(lb).hexdigest()
            same = "一致" if lh == h else "!!不一致!!"
            if lh != h:
                allok = False
            p(f"  {name:46s} {len(b):7d}B  线上={h[:16]} 本地={lh[:16]} {same}")
        else:
            p(f"  {name:46s} {len(b):7d}B  线上={h[:16]} (本地无此文件)")

    p("")
    p("=== 结论: " + ("skills/ 与关键文件全部落地一致 ✅" if allok else "存在缺失/不一致 ❌") + " ===")
    text = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
