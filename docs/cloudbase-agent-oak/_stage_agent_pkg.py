import io, os, sys, zipfile, urllib.request

# 下载链接不写死在源码里：COS 预签名 URL 的 q-ak 参数会带出 SecretId。
# 运行时取环境变量 BW_FUNC_CODE_URL，或第 1 个位置参数。
URL = os.environ.get("BW_FUNC_CODE_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not URL:
    raise SystemExit("用法: BW_FUNC_CODE_URL='<预签名URL>' python %s  （或把 URL 作为第 1 个参数）"
                     % os.path.basename(__file__))

STAGE = r"C:/temp/bw-agent"
FUNCDIR = os.path.join(STAGE, "agt-building-8gp5in9y2e59d69c")
os.makedirs(FUNCDIR, exist_ok=True)

print("downloading ...")
data = urllib.request.urlopen(URL, timeout=240).read()
z = zipfile.ZipFile(io.BytesIO(data))

skip = ("node_modules/",)
extracted = 0
for info in z.infolist():
    n = info.filename
    if n.startswith(skip) or n == "node_modules":
        continue
    z.extract(info, FUNCDIR)
    extracted += 1
print("extracted (excl node_modules):", extracted)

print("\n=== top-level of function dir ===")
for e in sorted(os.listdir(FUNCDIR)):
    p = os.path.join(FUNCDIR, e)
    print(("DIR  " if os.path.isdir(p) else "FILE "), e)

for f in ("package.json", "scf_bootstrap", "tsconfig.json"):
    p = os.path.join(FUNCDIR, f)
    if os.path.exists(p):
        print("\n===== %s =====" % f)
        print(open(p, "r", encoding="utf-8", errors="replace").read())
