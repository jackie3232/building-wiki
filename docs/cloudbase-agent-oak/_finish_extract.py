import os, zipfile, json, time

BASE = r"C:/temp/bw-agent"
ZIPPATH = os.path.join(BASE, "agt-building-8gp5in9y2e59d69c.original.zip")
FUNCDIR = os.path.join(BASE, "agt-building-8gp5in9y2e59d69c")

z = zipfile.ZipFile(ZIPPATH)
modes = {}
for name in ("agent.yaml", "scf_bootstrap", "package.json", "dist/index.js", "uid-shim.mjs"):
    try:
        zi = z.getinfo(name)
        modes[name] = {"mode": oct((zi.external_attr >> 16) & 0o7777), "size": zi.file_size,
                       "compress": zi.compress_type, "date": zi.date_time}
    except KeyError:
        modes[name] = "MISSING"
with open(os.path.join(BASE, "modes.json"), "w", encoding="utf-8") as f:
    json.dump(modes, f, ensure_ascii=False, indent=2)
print("MODES:", json.dumps(modes, ensure_ascii=False))

t0 = time.time()
print("extracting full ...", flush=True)
z.extractall(FUNCDIR)
cnt = sum(len(files) for _, _, files in os.walk(FUNCDIR))
print("DONE files=%d elapsed=%.1fs" % (cnt, time.time() - t0), flush=True)
with open(os.path.join(BASE, "extract.done"), "w") as f:
    f.write(str(cnt))
