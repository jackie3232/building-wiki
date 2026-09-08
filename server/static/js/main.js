// 工程数据发动机 · MVP 前端
// 全屏 Three.js 3D 场景 + 底部自然语言输入 → 逐个冒出 Box（体素）
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

/* ---------------- 场景基础 ---------------- */
const container = document.getElementById("scene-container");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf4f5f7);
scene.fog = new THREE.Fog(0xf4f5f7, 55, 110);

const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 200);
camera.position.set(18, 15, 18);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = false; // demo 不开启影，保持轻量
container.appendChild(renderer.domElement);

/* ---------------- 灯光 ---------------- */
scene.add(new THREE.AmbientLight(0xffffff, 0.75));
const dirLight = new THREE.DirectionalLight(0xffffff, 1.1);
dirLight.position.set(12, 22, 8);
scene.add(dirLight);
const rimLight = new THREE.DirectionalLight(0x6ea8fe, 0.35);
rimLight.position.set(-10, 6, -12);
scene.add(rimLight);

/* ---------------- 地面网格 ---------------- */
const grid = new THREE.GridHelper(44, 22, 0xb9c1cd, 0xdfe3ea);
grid.position.y = -0.01;
scene.add(grid);

/* ---------------- 控制器 ---------------- */
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.48;
controls.minDistance = 6;
controls.maxDistance = 60;
controls.target.set(0, 0.5, 0);

/* ---------------- Box 管理 ---------------- */
const boxRoot = new THREE.Group();
scene.add(boxRoot);

const SPAWN_INTERVAL = 260; // 每个 box 冒出间隔 ms
const BOX_SCALE = 1;        // 体素边长
const SPREAD = 9;           // 随机铺开半幅

const spawning = []; // 生长动画队列: {mesh, t}
const boxColors = [0x6ea8fe, 0x7c6ef5, 0x5ec9a6, 0xf0a35e, 0xef6f8f,
                   0x59c2e8, 0xa78bfa, 0x4ade80, 0xfbbf24, 0xfb7185];

function makeBoxMesh(x, y, z, color) {
  const geo = new THREE.BoxGeometry(BOX_SCALE, BOX_SCALE, BOX_SCALE);
  const mat = new THREE.MeshStandardMaterial({
    color, roughness: 0.42, metalness: 0.05,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(x, y, z);
  // 体素描边：我的世界感的关键
  const edge = new THREE.LineSegments(
    new THREE.EdgesGeometry(geo),
    new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35 })
  );
  mesh.add(edge);
  return mesh;
}

function randomFreePos(existing, half) {
  for (let attempt = 0; attempt < 12; attempt++) {
    const x = (Math.random() * 2 - 1) * half;
    const z = (Math.random() * 2 - 1) * half;
    const col = Math.round(x / BOX_SCALE);
    const row = Math.round(z / BOX_SCALE);
    if (!existing.has(`${col},${row}`)) {
      existing.add(`${col},${row}`);
      return { x: col * BOX_SCALE, z: row * BOX_SCALE };
    }
  }
  return null; // 铺满则放弃
}

const occupied = new Set();

function spawnBoxes(count) {
  for (let i = 0; i < count; i++) {
    const color = boxColors[i % boxColors.length];
    setTimeout(() => {
      const pos = randomFreePos(occupied, SPREAD);
      if (!pos) { setStatus("空间已铺满，先清空再试"); return; }
      const layer = Math.random() < 0.18 && occupied.size > 4 ? 1 : 0;
      const mesh = makeBoxMesh(pos.x, layer * BOX_SCALE + BOX_SCALE / 2, pos.z, color);
      mesh.scale.setScalar(0.01);
      boxRoot.add(mesh);
      spawning.push({ mesh, t: 0 });
    }, i * SPAWN_INTERVAL);
  }
}

function clearBoxes() {
  while (boxRoot.children.length) boxRoot.remove(boxRoot.children[0]);
  occupied.clear();
}

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

async function sendCommand() {
  const text = inputEl.value.trim();
  if (!text) return;

  sendEl.disabled = true;
  setStatus("正在理解…", true);
  try {
    const resp = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      setStatus(`出错了：${data.error || resp.status}`);
      return;
    }
    if (data.action === "clear") {
      clearBoxes();
      setStatus("场景已清空");
    } else {
      const n = data.count || 0;
      spawnBoxes(n);
      setStatus(`已创建 ${n} 个 Box`);
    }
  } catch (e) {
    setStatus(`网络错误：${e.message}`);
  } finally {
    sendEl.disabled = false;
    inputEl.value = "";
  }
}

sendEl.addEventListener("click", sendCommand);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendCommand();
});
clearBtn.addEventListener("click", () => { clearBoxes(); setStatus("场景已清空"); });

/* ---------------- 生长动画 + 渲染循环 ---------------- */
function animate() {
  requestAnimationFrame(animate);

  // 冒出的 box：从 0 弹到 1
  for (let i = spawning.length - 1; i >= 0; i--) {
    const s = spawning[i];
    s.t += 0.06;
    const k = Math.min(1, s.t);
    const ease = 1 - Math.pow(1 - k, 3); // easeOutCubic
    s.mesh.scale.setScalar(0.01 + 0.99 * ease);
    if (k >= 1) spawning.splice(i, 1);
  }

  controls.update();
  renderer.render(scene, camera);
}

/* ---------------- 自适应 ---------------- */
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

animate();
