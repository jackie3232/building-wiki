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
  while (boxRoot.children.length) {
    const o = boxRoot.children[0];
    boxRoot.remove(o);
    if (o.geometry) o.geometry.dispose();
    if (o.material) o.material.dispose();
  }
}

function addBoxes(boxes) {
  clearBoxes();
  for (const b of boxes) {
    const geo = new THREE.BoxGeometry(b.w, b.h, b.d);
    const col = new THREE.Color(b.color !== undefined ? b.color : 0x999999);
    const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.72, metalness: 0.05 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(b.x, b.y, b.z);
    mesh.userData = { role: b.role, label: b.label };
    boxRoot.add(mesh);
  }
  fitCameraToObject(boxRoot);
  return boxes.length;
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
  pointer.x = (e.clientX / innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(boxRoot.children, false);
  if (hits.length) {
    const u = hits[0].object.userData;
    setStatus(`选中：${u.label || u.role || "未知"}`, false);
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
    setStatus(`已生成体素模型 · ${n} 个构件`);
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
