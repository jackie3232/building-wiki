import io, os, sys, zipfile, urllib.request, json

# 下载链接不写死在源码里：COS 预签名 URL 的 q-ak 参数会带出 SecretId。
# 运行时取环境变量 BW_FUNC_CODE_URL，或第 1 个位置参数。
URL = os.environ.get("BW_FUNC_CODE_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not URL:
    raise SystemExit("用法: BW_FUNC_CODE_URL='<预签名URL>' python %s  （或把 URL 作为第 1 个参数）"
                     % os.path.basename(__file__))

BASE = r"C:/temp/bw-agent"
os.makedirs(BASE, exist_ok=True)
ZIPPATH = os.path.join(BASE, "agt-building-8gp5in9y2e59d69c.original.zip")
FUNCDIR = os.path.join(BASE, "agt-building-8gp5in9y2e59d69c")

if not os.path.exists(ZIPPATH):
    print("downloading original package ...")
    data = urllib.request.urlopen(URL, timeout=300).read()
    with open(ZIPPATH, "wb") as f:
        f.write(data)
    print("saved", ZIPPATH, len(data), "bytes")
else:
    print("reuse saved", ZIPPATH, os.path.getsize(ZIPPATH), "bytes")

z = zipfile.ZipFile(ZIPPATH)
for name in ("agent.yaml", "scf_bootstrap", "package.json", "dist/index.js"):
    try:
        zi = z.getinfo(name)
        mode = (zi.external_attr >> 16) & 0o7777
        print("MODE %-18s %s  size=%d" % (name, oct(mode), zi.file_size))
    except KeyError:
        print("MISSING", name)

print("\nextracting full package (incl node_modules) ...")
z.extractall(FUNCDIR)
cnt = sum(len(files) for _, _, files in os.walk(FUNCDIR))
print("files on disk:", cnt)

sb = os.path.join(FUNCDIR, "scf_bootstrap")
print("scf_bootstrap exists:", os.path.exists(sb))

# record a manifest of the zip for later surgical rebuild
man = [(i.filename, i.file_size, (i.external_attr >> 16) & 0o7777, i.date_time, i.compress_type) for i in z.infolist()]
with open(os.path.join(BASE, "original_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(man, f)
print("manifest entries:", len(man))
