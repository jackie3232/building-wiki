import io, os, sys, zipfile, urllib.request

# 下载链接不写死在源码里：COS 预签名 URL 的 q-ak 参数会带出 SecretId。
# 运行时取环境变量 BW_FUNC_CODE_URL，或第 1 个位置参数。
URL = os.environ.get("BW_FUNC_CODE_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not URL:
    raise SystemExit("用法: BW_FUNC_CODE_URL='<预签名URL>' python %s  （或把 URL 作为第 1 个参数）"
                     % os.path.basename(__file__))

OUT = r"D:/sourcecodes/building.wiki/docs/cloudbase-agent-oak/_live_pkg"
os.makedirs(OUT, exist_ok=True)

print("downloading ...")
data = urllib.request.urlopen(URL, timeout=180).read()
print("bytes:", len(data))

z = zipfile.ZipFile(io.BytesIO(data))
names = z.namelist()
print("entries:", len(names))

# top-level layout
tops = sorted(set(n.split("/")[0] for n in names))
print("top-level:", tops)

# find candidate config-ish files
for n in names:
    low = n.lower()
    if low.endswith("agent.yaml") or low.endswith("agent.yml") or "config" in low and low.count("/") < 3:
        print("MATCH:", n)

# extract agent.yaml anywhere
for n in names:
    if n.lower().endswith(("agent.yaml", "agent.yml")):
        z.extract(n, OUT)
        p = os.path.join(OUT, n)
        print("=== extracted:", p, "===")
        with open(p, "rb") as f:
            print(f.read().decode("utf-8", "replace"))
