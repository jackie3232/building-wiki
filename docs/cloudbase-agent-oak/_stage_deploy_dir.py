import os, shutil, zipfile

BASE = r"C:/temp/bw-agent"
ZIPPATH = os.path.join(BASE, "agt-building-8gp5in9y2e59d69c.original.zip")
REPO_YAML = r"D:/sourcecodes/building.wiki/docs/cloudbase-agent-oak/agent.yaml"
AGENTDIR = os.path.join(BASE, "agent-code")   # the agent code dir (files at top level)

if os.path.isdir(AGENTDIR):
    shutil.rmtree(AGENTDIR)
os.makedirs(AGENTDIR, exist_ok=True)

z = zipfile.ZipFile(ZIPPATH)
n = 0
for info in z.infolist():
    name = info.filename
    if name.startswith("node_modules/") or name == "node_modules":
        continue
    z.extract(info, AGENTDIR)
    n += 1
print("extracted source files:", n)

# overwrite agent.yaml with the corrected repo version
shutil.copyfile(REPO_YAML, os.path.join(AGENTDIR, "agent.yaml"))
print("agent.yaml replaced with repo corrected version")

print("\n=== agent-code top level ===")
for e in sorted(os.listdir(AGENTDIR)):
    p = os.path.join(AGENTDIR, e)
    print(("DIR  " if os.path.isdir(p) else "FILE "), e)

print("\n=== dist/ ===")
d = os.path.join(AGENTDIR, "dist")
if os.path.isdir(d):
    for root, dirs, files in os.walk(d):
        rel = os.path.relpath(root, AGENTDIR)
        for f in files:
            print("   ", os.path.join(rel, f))

print("\n=== src/ ===")
s = os.path.join(AGENTDIR, "src")
if os.path.isdir(s):
    for root, dirs, files in os.walk(s):
        rel = os.path.relpath(root, AGENTDIR)
        for f in files:
            print("   ", os.path.join(rel, f))

print("\n=== agent.yaml content ===")
print(open(os.path.join(AGENTDIR, "agent.yaml"), encoding="utf-8").read())
