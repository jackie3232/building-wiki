#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""四合院体素预览回路 —— 一条命令，把骨架跑成浏览器里能转的 3D 模型。

    python tools/preview/preview.py                      # 默认：单进院 + 本地服务
    python tools/preview/preview.py --skeleton sk.json   # 指定骨架文件
    python tools/preview/preview.py --port 8888
    python tools/preview/preview.py --standalone         # 只产出单文件 view.html，不起服务

链路：
    骨架(skeleton)  --[assemble.mjs]-->  实例图谱(instance)
                    --[④ compute_geometry / ⑤ geometry_to_boxes]-->  体素(boxes)
                    --[本地静态服务 / 单文件 HTML]-->  浏览器渲染

产物落在 tools/preview/out/（已 gitignore，不入库）。
改知识包、改引擎后重跑本脚本即可看到新结果——这是开发期的「眼睛」。

--standalone 产出的 out/view.html 是**自包含单文件**（three.js / OrbitControls / 体素数据
全部内联），双击即开、不需要服务、不依赖任何相对路径——用来把结果直接递给别人看。
"""
import argparse
import base64
import functools
import glob
import http.server
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # 项目根
OUT = os.path.join(HERE, "out")

# 默认骨架 = 单进院（对应 pack 里 rules.occupancy 的 single 条）
DEFAULT_SKELETON = {
    "style": "siheyuan",
    "jin": 1,
    "courtyards": [
        {
            "sequence": 1,
            "enclosure": {
                "bei": {"role": "zhengfang"},
                "nan": {"role": "daozuofang", "gate": {"role": "zhaimen"}},
                "dong": {"role": "xiangfang"},
                "xi": {"role": "xiangfang"},
            },
            "peripheral": [{"role": "yingbi"}],
            "perimeter": True,
        }
    ],
}


def find_assemble():
    hits = glob.glob(os.path.join(
        ROOT, "functions", "*", "skills", "traditional-building", "assemble.mjs"))
    if not hits:
        sys.exit("找不 assemble.mjs（预期在 functions/*/skills/traditional-building/ 下）")
    return hits[0]


def find_node():
    n = os.environ.get("NODE_BIN") or shutil.which("node")
    if not n:
        sys.exit("找不 node。请把 node 放进 PATH，或用环境变量 NODE_BIN 指定绝对路径。")
    return n


def data_url(path):
    """本地 JS 文件 -> data: URL（供 importmap 用）。
    这样单文件 HTML 里的 ES module 依赖（three / OrbitControls）无需任何外部路径。
    注意：不必担心 three.js 里出现 `</script>`——它作为 data: URL 出现在属性里，不进 <script> 正文。"""
    b = io.open(path, "rb").read()
    return "data:text/javascript;base64," + base64.b64encode(b).decode("ascii")


STANDALONE_TMPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;overflow:hidden;background:#f2f1ee;
            font:13px/1.5 system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
  #hud{position:fixed;left:12px;top:12px;z-index:9;background:rgba(255,255,255,.92);
       border:1px solid #ddd;border-radius:8px;padding:8px 12px;color:#333;pointer-events:none}
  #hud b{font-weight:600}
  #hud span{color:#666}
  #legend{position:fixed;right:12px;top:12px;z-index:9;background:rgba(255,255,255,.92);
          border:1px solid #ddd;border-radius:8px;padding:8px 10px;color:#333;max-height:80vh;overflow:auto}
  #legend div{display:flex;align-items:center;gap:6px;line-height:1.9}
  #legend i{width:12px;height:12px;border-radius:2px;display:inline-block;border:1px solid #0002}
</style>
</head>
<body>
<div id="hud"><b>__TITLE__</b><br><span id="stat">加载中…</span></div>
<div id="legend"></div>
<script type="importmap">
{ "imports": { "three": "__THREE__", "orbit": "__ORBIT__" } }
</script>
<script id="boxes" type="application/json">__BOXES__</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'orbit';

const boxes = JSON.parse(document.getElementById('boxes').textContent);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf2f1ee);
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 2000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio);
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
scene.add(new THREE.AmbientLight(0xffffff, 1.9));
const dl = new THREE.DirectionalLight(0xffffff, 1.6); dl.position.set(30, 60, 20); scene.add(dl);
const dl2 = new THREE.DirectionalLight(0xffffff, 0.5); dl2.position.set(-30, 20, -30); scene.add(dl2);

const groups = {};
for (const b of boxes) (groups[b.role] ||= []).push(b);
const unit = new THREE.BoxGeometry(1, 1, 1);
const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), v = new THREE.Vector3(), s = new THREE.Vector3();
for (const [role, list] of Object.entries(groups)) {
  const im = new THREE.InstancedMesh(unit, new THREE.MeshLambertMaterial({ color: list[0].color }), list.length);
  list.forEach((b, i) => { v.set(b.x, b.y, b.z); s.set(b.w, b.h, b.d); m4.compose(v, q, s); im.setMatrixAt(i, m4); });
  im.instanceMatrix.needsUpdate = true;
  scene.add(im);
}
const bb = new THREE.Box3().setFromObject(scene);
const c = bb.getCenter(new THREE.Vector3());
const size = bb.getSize(new THREE.Vector3());
controls.target.copy(c);
camera.position.copy(c).add(new THREE.Vector3(size.x * 0.9, size.z * 0.8, size.z * 1.15));
controls.update();

const hex = (n) => '#' + n.toString(16).padStart(6, '0');
const counts = Object.entries(groups)
  .map(([r, l]) => [r, l.length, l[0].label, l[0].color])
  .sort((a, b) => b[1] - a[1]);
document.getElementById('legend').innerHTML = counts.map(([r, n, label, col]) =>
  `<div><i style="background:${hex(col)}"></i>${label} <span style="color:#888">${n}</span></div>`).join('');
document.getElementById('stat').textContent =
  boxes.length + ' 体素 · ' + counts.length + ' 类构件 · ' + size.x.toFixed(1) + '×' + size.z.toFixed(1) + ' m';

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
(function loop(){ requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
</script>
</body>
</html>
"""


def write_standalone(boxes, title):
    """产出**自包含**单文件 HTML：three.js / OrbitControls / 体素数据全内联。"""
    three = os.path.join(ROOT, "web", "vendor", "three.module.min.js")
    orbit = os.path.join(ROOT, "web", "vendor", "OrbitControls.js")
    html = (STANDALONE_TMPL
            .replace("__TITLE__", title)
            .replace("__THREE__", data_url(three))
            .replace("__ORBIT__", data_url(orbit))
            .replace("__BOXES__", json.dumps(boxes, ensure_ascii=False, separators=(",", ":"))))
    p = os.path.join(OUT, "view.html")
    io.open(p, "w", encoding="utf-8").write(html)
    return p


def main():
    ap = argparse.ArgumentParser(description="四合院体素预览回路")
    ap.add_argument("--skeleton", help="骨架 JSON 文件；不传则用内置单进院")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--standalone", action="store_true",
                    help="只产出自包含单文件 out/view.html，不起本地服务")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    assemble = find_assemble()
    skill_dir = os.path.dirname(assemble)
    node = find_node()

    # 1) 骨架
    if args.skeleton:
        raw = io.open(args.skeleton, encoding="utf-8").read()
    else:
        raw = json.dumps(DEFAULT_SKELETON, ensure_ascii=False)
    sk_path = os.path.join(OUT, "skeleton.json")
    io.open(sk_path, "w", encoding="utf-8").write(raw)
    plan = json.loads(raw)
    print("[1/4] 骨架：jin=%s" % plan.get("jin"))

    # 2) 装配：骨架 -> 实例图谱（不碰盘包之外的东西）
    proc = subprocess.run(
        [node, assemble, "--skeleton", sk_path],
        cwd=skill_dir, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        sys.exit("装配失败（图谱缺陷）：\n" + (proc.stderr or proc.stdout))
    inst_path = os.path.join(OUT, "instance.json")
    io.open(inst_path, "w", encoding="utf-8").write(proc.stdout)
    inst = json.loads(proc.stdout)
    print("[2/4] 实例图谱：%d 进 · %d 字节" % (inst.get("data", {}).get("jin", 0), len(proc.stdout)))

    # 3) ④⑤：实例图谱 -> 体素（直接复用服务端引擎，不复制一份）
    sys.path.insert(0, os.path.join(ROOT, "server"))
    from engine.geometry import instance_to_boxes  # noqa: E402
    boxes = instance_to_boxes(inst)
    io.open(os.path.join(OUT, "boxes.json"), "w", encoding="utf-8").write(
        json.dumps(boxes, ensure_ascii=False))
    roles = {}
    for b in boxes:
        roles[b.get("role")] = roles.get(b.get("role"), 0) + 1
    print("[3/4] 体素：%d 块 · %d 类 %s" % (len(boxes), len(roles), sorted(roles)))

    # 4) 呈现：自包含单文件 / 本地静态服务（root = 项目根，可复用 web/vendor 的 three.js）
    if args.standalone:
        names = " · ".join(c.get("name", "") for c in inst["data"]["courtyards"])
        p = write_standalone(boxes, "四合院 · %d 进（%s）" % (inst["data"]["jin"], names))
        print("[4/4] 自包含单文件已写出（双击即开）：\n      %s\n" % p)
        return

    http.server.SimpleHTTPRequestHandler.extensions_map[".js"] = "text/javascript"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    url = "http://127.0.0.1:%d/tools/preview/index.html" % args.port
    print("[4/4] 预览已就绪（Ctrl+C 停止）：\n      %s\n" % url)
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")


if __name__ == "__main__":
    main()
