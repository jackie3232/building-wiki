"""知识中心 -> skill 同步（过渡期工具，2026-09-22）

背景：知识中心当前住在 server/knowledge/（服务端），但按分层它只服务**智能化侧**。
目标终局是它搬到 Agent 侧（skill 内）成为唯一源。搬迁前提：先修 ⑤ 的 label 漏读
（geometry_to_boxes L1363 / build_tour_path L836,L855 还在读磁盘 dict.json），否则服务端会断。

本脚本是**过渡手段**：把知识中心三件套按需复制进 skill，让 skill 可以先上线验证。
- 源（唯一事实源，勿改生成物）：server/knowledge/
- 目标：docs/cloudbase-agent-oak/skill/skills/siheyuan/knowledge/
- 生成物每份首行会被写入 __generated__ 标记，提醒勿手改（改了会被下次同步覆盖）。

用法：server/.venv/Scripts/python.exe docs/cloudbase-agent-oak/_sync_knowledge.py [--check]
       --check 只比对不写，非零退出表示已漂移。
"""
import json
import os
import sys

ROOT = r"D:\sourcecodes\building.wiki"
SRC = os.path.join(ROOT, "server", "knowledge")
DST = os.path.join(ROOT, "docs", "cloudbase-agent-oak", "skill", "skills", "siheyuan", "knowledge")
FILES = ["dict.json", "siheyuan.rules", "siheyuan.type.json"]
MARK = "__generated__"


def main():
    check = "--check" in sys.argv
    os.makedirs(DST, exist_ok=True)
    rc = 0
    for name in FILES:
        s, d = os.path.join(SRC, name), os.path.join(DST, name)
        src_text = open(s, encoding="utf-8").read()
        # 生成物快照：源 + __generated__ 标记（不改内容语义，仅提示来源）
        doc = json.loads(src_text)
        if isinstance(doc, dict):
            doc[MARK] = {"source": "server/knowledge/" + name,
                         "note": "生成物，勿手改；改动请改源后重跑 _sync_knowledge.py"}
        want = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if check:
            have = open(d, encoding="utf-8").read() if os.path.exists(d) else None
            if have != want:
                print(f"[DRIFT] {name}")
                rc = 1
            else:
                print(f"[OK]    {name}")
            continue
        with open(d, "w", encoding="utf-8", newline="\n") as f:
            f.write(want)
        print(f"synced  {name}  ({len(want)} bytes)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
