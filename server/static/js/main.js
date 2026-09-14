// BUILDING.WIKI · MVP 前端（体素 Box 版，取代原 STL 渲染）
// 链路：NL/图谱 -> /api/command -> {action:"model", boxes:[...]} -> Three.js 体素
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

/* ---------------- 场景基础 ---------------- */
const container = document.getElementById("scene-container");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf4f5f7);
scene.fog = new THREE.Fog(0xf4f5f7, 60, 160);

const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 500);
camera.position.set(45, 38, 45);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
container.appendChild(renderer.domElement);

/* ---------------- 灯光 ---------------- */
scene.add(new THREE.AmbientLight(0xffffff, 0.8));
const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
dirLight.position.set(20, 40, 15);
scene.add(dirLight);

/* ---------------- 地面网格 ---------------- */
const grid = new THREE.GridHelper(1000, 1000, 0xb9c1cd, 0xdfe3ea);
grid.position.y = -0.01;
scene.add(grid);
let modelCenter = new THREE.Vector3();

/* ---------------- 控制器 ---------------- */
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 8;
controls.maxDistance = 200;
controls.target.set(0, 0.5, 0);

/* ---------------- 体素根 ---------------- */
const boxRoot = new THREE.Group();
scene.add(boxRoot);

function clearBoxes() {
  if (voxMesh) {
    boxRoot.remove(voxMesh);
    voxMesh.geometry.dispose();
    voxMesh.material.dispose();
    voxMesh = null;
  }
  if (voxEdges) {
    boxRoot.remove(voxEdges);
    voxEdges.geometry.dispose();
    voxEdges.material.dispose();
    voxEdges = null;
  }
}

let voxMesh = null;
let voxEdges = null;

function addBoxes(boxes) {
  clearBoxes();
  if (!boxes.length) return 0;
  // 体素数量可达上万 -> 用 InstancedMesh 单次 draw call 渲染，避免逐 block 卡死
  const geo = new THREE.BoxGeometry(1, 1, 1);
  const mat = new THREE.MeshStandardMaterial({ roughness: 0.72, metalness: 0.05 });
  voxMesh = new THREE.InstancedMesh(geo, mat, boxes.length);
  const m = new THREE.Matrix4();
  const p = new THREE.Vector3();
  const q = new THREE.Quaternion();
  const s = new THREE.Vector3();
  const col = new THREE.Color();
  const FILL = 0.92;   // 实心块微缩留缝，配合边线呈现体素网格感
  for (let i = 0; i < boxes.length; i++) {
    const b = boxes[i];
    p.set(b.x, b.y, b.z);
    s.set(b.w * FILL, b.h * FILL, b.d * FILL);
    m.compose(p, q, s);
    voxMesh.setMatrixAt(i, m);
    col.set(b.color !== undefined ? b.color : 0x999999);
    voxMesh.setColorAt(i, col);
  }
  voxMesh.instanceMatrix.needsUpdate = true;
  if (voxMesh.instanceColor) voxMesh.instanceColor.needsUpdate = true;
  voxMesh.userData.boxes = boxes;   // 供点选反查构件名
  boxRoot.add(voxMesh);
  addBoxEdges(boxes);                // 叠加每个体素的边框线，凸显体素结构
  fitCameraToObject(boxRoot);
  return boxes.length;
}

// 每个体素描一圈边框线（合并为单条 LineSegments，颜色取所属构件色加深），呈现体素划分
function addBoxEdges(boxes) {
  const tmpl = [
    [-0.5,-0.5,-0.5],[0.5,-0.5,-0.5], [0.5,-0.5,-0.5],[0.5,0.5,-0.5],
    [0.5,0.5,-0.5],[-0.5,0.5,-0.5], [-0.5,0.5,-0.5],[-0.5,-0.5,-0.5],
    [-0.5,-0.5,0.5],[0.5,-0.5,0.5], [0.5,-0.5,0.5],[0.5,0.5,0.5],
    [0.5,0.5,0.5],[-0.5,0.5,0.5], [-0.5,0.5,0.5],[-0.5,-0.5,0.5],
    [-0.5,-0.5,-0.5],[-0.5,-0.5,0.5], [0.5,-0.5,-0.5],[0.5,-0.5,0.5],
    [0.5,0.5,-0.5],[0.5,0.5,0.5], [-0.5,0.5,-0.5],[-0.5,0.5,0.5],
  ];
  const verts = new Float32Array(boxes.length * tmpl.length * 3);
  const cols = new Float32Array(boxes.length * tmpl.length * 3);
  const c = new THREE.Color();
  let o = 0;
  for (const b of boxes) {
    c.set(b.color !== undefined ? b.color : 0x999999).multiplyScalar(0.5); // 边线加深以凸显
    for (const t of tmpl) {
      verts[o] = b.x + t[0] * b.w; verts[o + 1] = b.y + t[1] * b.h; verts[o + 2] = b.z + t[2] * b.d;
      cols[o] = c.r; cols[o + 1] = c.g; cols[o + 2] = c.b;
      o += 3;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(verts, 3));
  g.setAttribute("color", new THREE.BufferAttribute(cols, 3));
  const m = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.6 });
  voxEdges = new THREE.LineSegments(g, m);
  boxRoot.add(voxEdges);
}

function fitCameraToObject(obj) {
  const bb = new THREE.Box3().setFromObject(obj);
  if (bb.isEmpty()) return;
  const size = bb.getSize(new THREE.Vector3());
  const center = bb.getCenter(new THREE.Vector3());
  modelCenter.copy(center);
  const radius = Math.max(size.length() * 0.5, 1e-3);
  const fov = (camera.fov * Math.PI) / 180;
  const dist = (radius / Math.sin(fov / 2)) * 1.2;
  const d = new THREE.Vector3(1, 0.8, 1).normalize();
  controls.minDistance = radius * 0.4;
  controls.maxDistance = dist * 4;
  controls.target.copy(center);
  controls.object.position.copy(center).addScaledVector(d, dist);
  controls.update();
  controls.object.position.copy(center).addScaledVector(d, dist);
  controls.update();
  camera.near = Math.max(dist / 1000, 0.01);
  camera.far = dist * 20;
  camera.updateProjectionMatrix();
  grid.position.y = bb.min.y - 0.01;
  scene.fog.near = dist * 0.8;
  scene.fog.far = dist * 4;
}

/* ---------------- 点选看 label ---------------- */
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downXY = null;
renderer.domElement.addEventListener("pointerdown", (e) => { downXY = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!downXY) return;
  const moved = Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]);
  downXY = null;
  if (moved > 5) return; // 拖拽不算点选
  if (!voxMesh) return;
  pointer.x = (e.clientX / innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObject(voxMesh, false);
  if (hits.length) {
    const id = hits[0].instanceId;
    const b = voxMesh.userData.boxes[id];
    setStatus(`选中：${b.label || b.role || "未知"}`, false);
  }
});

/* ---------------- 输入交互 ---------------- */
const inputEl = document.getElementById("cmd-input");
const sendEl = document.getElementById("cmd-send");
const statusEl = document.getElementById("hud-status");
const clearBtn = document.getElementById("btn-clear");

let statusTimer = null;
function setStatus(msg, busy = false) {
  statusEl.textContent = msg || "";
  statusEl.classList.toggle("busy", busy);
  statusEl.classList.remove("hidden");
  clearTimeout(statusTimer);
  if (!busy) statusTimer = setTimeout(() => statusEl.classList.add("hidden"), 2600);
}

async function renderResponse(data) {
  if (data.action === "clear") {
    if (data.source === "error") { setStatus(`出错了：${data.error || ""}`); return; }
    clearBoxes(); setStatus("场景已清空"); return;
  }
  if (Array.isArray(data.boxes)) {
    const n = addBoxes(data.boxes);
    setStatus(`已生成体素模型 · ${n} 个体素`);
    return;
  }
  setStatus("未返回几何数据");
}

async function postCommand(payload) {
  sendEl.disabled = true;
  setStatus("正在生成…", true);
  try {
    const resp = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) { setStatus(`出错了：${data.error || resp.status}`); return; }
    await renderResponse(data);
  } catch (e) {
    setStatus(`网络错误：${e.message}`);
  } finally {
    sendEl.disabled = false;
  }
}

async function sendCommand() {
  const text = inputEl.value.trim();
  if (!text) return;
  if (text.startsWith("{") || text.startsWith("[")) {
    try { await postCommand({ graph: JSON.parse(text) }); inputEl.value = ""; return; }
    catch (e) { setStatus("以 { 开头但不是合法 JSON，按文本处理"); }
  }
  await postCommand({ text });
  inputEl.value = "";
}

const uploadBtn = document.getElementById("btn-upload");
const fileInput = document.getElementById("graph-file");
uploadBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = () => {
    try { postCommand({ graph: JSON.parse(r.result) }); }
    catch (err) { setStatus(`文件不是合法 JSON：${err.message}`); }
    fileInput.value = "";
  };
  r.readAsText(f);
});

sendEl.addEventListener("click", sendCommand);
inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") sendCommand(); });
clearBtn.addEventListener("click", () => { clearBoxes(); setStatus("场景已清空"); });

/* ---------------- 渲染循环 ---------------- */
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  grid.position.x = Math.round(modelCenter.x);
  grid.position.z = Math.round(modelCenter.z);
  renderer.render(scene, camera);
}
animate();
