// 工程数据发动机 · MVP 前端
// 全屏 Three.js 3D 场景 + 底部自然语言输入 → 显示真实几何（STL，含门/窗开口）
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

/* ---------------- 真实几何（STL，含门/窗开口） ---------------- */
// OCCT 导出的 STL 为 mm、Z-up（X=东-西, Y=南-北, Z=竖向）。
// 渲染时做「Y/Z 互换 + scale 0.001」变换，落到场景坐标（米）。
const stlRoot = new THREE.Group();
scene.add(stlRoot);

let currentSTL = null;            // 当前已加载的真实几何 mesh

// 自包含 STL 解析（不依赖外部 loader，离线可用）：ASCII 优先，二进制兜底。
// 返回 THREE.BufferGeometry（mm, Z-up）。
//
// 历史注记：此处曾有「按面积阈值剔除楼板/屋顶大平板」的逻辑（isHorizontalPlateLayer +
// dropZ）。该逻辑是为绕开「庭院被误判为室内 → 盖满楼板/屋顶 → 看似大盒子」的问题，但
// 那只治标：编码对齐从源头修复后（voxelcli 侧把名称转 GBK 送引擎），引擎已能正确判定
// 庭院/室内，不再给庭院盖板，无需前端剔除。且该剔除会**拆散板的对偶面**（如楼板底面
// z=0 被剔、只剩顶面 z=300），把有厚度的板变成无厚度单层薄片，正是「一个个面片」的来源。
// 故彻底移除，STL 原样渲染。
function parseSTLText(text, opts) {
  opts = opts || {};
  const positions = [];
  const normals = [];
  const re = /facet\s+normal\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)[\s\S]*?vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)/g;

  let m;
  let count = 0;
  while ((m = re.exec(text)) !== null) {
    const nx = parseFloat(m[1]), ny = parseFloat(m[2]), nz = parseFloat(m[3]);
    for (let i = 0; i < 3; i++) {
      const b = 4 + i * 3;
      positions.push(parseFloat(m[b]), parseFloat(m[b + 1]), parseFloat(m[b + 2]));
      normals.push(nx, ny, nz);
    }
    count++;
  }
  if (opts.onStats) opts.onStats({ total: count });

  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  return g;
}

function parseSTLBinary(buf) {
  const dv = new DataView(buf);
  const tris = dv.getUint32(80, true);
  const positions = [];
  const normals = [];
  let off = 84;
  for (let i = 0; i < tris; i++) {
    const nx = dv.getFloat32(off, true), ny = dv.getFloat32(off + 4, true), nz = dv.getFloat32(off + 8, true);
    for (let v = 0; v < 3; v++) {
      positions.push(
        dv.getFloat32(off + 12 + v * 12, true),
        dv.getFloat32(off + 16 + v * 12, true),
        dv.getFloat32(off + 20 + v * 12, true)
      );
      normals.push(nx, ny, nz);
    }
    off += 50;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  return g;
}

// 把 STL 几何变换到与 box 视图一致的坐标系：Z-up → Y-up，并 mm → m。
//
// 这里用「互换 Y/Z」的矩阵（行列式 -1，属镜像反射）：newX = X, newY = Z, newZ = Y。
// 它会翻转三角面的绕序（winding），因此随后 computeVertexNormals() 按新绕序算出的法线
// 会指向实体内部（与 STL 原始外向法线相反）。
//
// 但这在本项目里不构成问题：材质用的是 THREE.DoubleSide，three.js 片元着色器在
// DOUBLE_SIDED 分支下会依据 gl_FrontFacing 把背面法线取反
//   float faceDirection = gl_FrontFacing ? 1.0 : -1.0;  normal *= faceDirection;
// 于是无论法线存的是内向还是外向，「朝向相机可见面」的最终着色都等价——这也是「面片」
// 观感的真正来源是此前的楼板/屋顶剔除、而非矩阵的原因。镜像与旋转矩阵在 DoubleSide 下
// 效果一致，唯一可感知差异只是镜像会把模型南北方向翻转一次；既然着色无实质收益，就
// 保持本来的镜像矩阵，不引入多余改动。
function transformToScene(geo) {
  const m = new THREE.Matrix4().set(
    1, 0, 0, 0,
    0, 0, 1, 0,
    0, 1, 0, 0,
    0, 0, 0, 1
  );
  geo.applyMatrix4(m);
  geo.scale(0.001, 0.001, 0.001);
  geo.computeVertexNormals();
  return geo;
}

async function loadSTL(filename) {
  const resp = await fetch("/api/asset/" + encodeURIComponent(filename));
  if (!resp.ok) throw new Error("STL 获取失败 " + resp.status);
  const buf = await resp.arrayBuffer();
  const head = new Uint8Array(buf, 0, Math.min(5, buf.byteLength));
  const isASCII = String.fromCharCode(...head).toLowerCase().startsWith("solid");
  const stats = {};
  const geo = isASCII
    ? parseSTLText(new TextDecoder().decode(buf), { onStats: (s) => Object.assign(stats, s) })
    : parseSTLBinary(buf);
  if (stats.total) {
    console.log(`[STL] 三角面 ${stats.total}（原样渲染，不做任何剔除）`);
  }
  transformToScene(geo);
  // 该 STL 由一块块独立 box / 薄板拼出，大量面是单层薄壳（楼板/屋顶多为单面），
  // 必须 DoubleSide 渲染背面，否则从缝隙/内侧看进去全是空的（实测去掉后"看到的更少"）。
  const mesh = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: 0x9aa3af, roughness: 0.6, metalness: 0.05, side: THREE.DoubleSide })
  );
  return mesh;
}

/* 按模型包围盒自动取景：相机拉到能完整俯瞰整个模型的位置与距离。
   尺寸差异极大（模型 25m 见方，早期相机参数是为小体素定的），不自动适配就会糊在一面墙上。 */
function fitCameraToObject(object) {
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) return;
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  // 以包围盒半径和相机 FOV 反算恰好容纳所需的距离
  const radius = Math.max(size.length() * 0.5, 1e-3);
  const fovRad = (camera.fov * Math.PI) / 180;
  const dist = (radius / Math.sin(fovRad / 2)) * 1.15; // 15% 余量

  // 等轴俯视方向（右上后方），保证一眼看清整体
  const dir = new THREE.Vector3(1, 0.85, 1).normalize();

  // OrbitControls 的 update() 每帧会用「target + spherical」重算并覆盖 camera.position，
  // 直接赋 camera.position 会在下一帧被拽回旧位置（这是之前改了没生效的原因）。
  // 可靠做法：设好 target 与距离，再由 target+dir 显式写回相机位置，并让 controls 重新同步。
  controls.minDistance = radius * 0.4;
  controls.maxDistance = dist * 4;
  controls.target.copy(center);
  controls.object.position.copy(center).addScaledVector(dir, dist);
  controls.update();
  // update() 之后再次写回，确保本帧与后续帧都以新位置为准（damping 会缓存增量）
  controls.object.position.copy(center).addScaledVector(dir, dist);
  controls.update();

  camera.near = Math.max(dist / 1000, 0.01);
  camera.far = dist * 20;
  camera.updateProjectionMatrix();

  // 地面网格随模型尺度调整，避免尺度错配
  const span = Math.max(size.x, size.z);
  grid.scale.setScalar(span / 44);
  grid.position.y = box.min.y - 0.01;
  scene.fog.near = dist * 0.8;
  scene.fog.far = dist * 3;
}

function clearSTL() {
  while (stlRoot.children.length) {
    const c = stlRoot.children[0];
    stlRoot.remove(c);
    if (c.geometry) c.geometry.dispose();
    if (c.material) c.material.dispose();
  }
  currentSTL = null;
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

// 渲染响应：清场 / 真实几何（STL）
async function renderResponse(data, label) {
  if (data.action === "clear") {
    if (data.source === "error") { setStatus(`出错了：${data.error || "未知错误"}`); return; }
    clearSTL();
    setStatus("场景已清空");
    return;
  }
  if (data.stl) {
    clearSTL();
    try {
      setStatus("正在加载真实几何…", true);
      currentSTL = await loadSTL(data.stl);
      stlRoot.add(currentSTL);
      fitCameraToObject(currentSTL);
      const n = data.boxes ? data.boxes.length : 0;
      setStatus(`已生成真实几何${n ? " · " + n + " 个构件" : ""}${label ? " · " + label : ""}`);
    } catch (e) {
      console.warn("STL 加载失败：", e);
      setStatus("真实几何加载失败");
    }
    return;
  }
  setStatus("未返回几何数据");
}

async function sendGraph(obj, label) {
  sendEl.disabled = true;
  setStatus("正在生成…", true);
  try {
    const resp = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph: obj }),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      setStatus(`出错了：${data.error || resp.status}`);
      return;
    }
    await renderResponse(data, label);
  } catch (e) {
    setStatus(`网络错误：${e.message}`);
  } finally {
    sendEl.disabled = false;
  }
}

async function sendCommand() {
  const text = inputEl.value.trim();
  if (!text) return;

  // 以 { 或 [ 开头 → 视为粘贴的图谱 JSON，直接上传生成
  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      const obj = JSON.parse(text);
      await sendGraph(obj, "来自粘贴");
      inputEl.value = "";
      return;
    } catch (e) {
      setStatus("输入以 { 开头但不是合法 JSON，按文本处理");
    }
  }

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
      if (data.source === "error") { setStatus(`出错了：${data.error || "未知错误"}`); return; }
      clearSTL();
      setStatus("场景已清空");
    } else if (data.stl) {
      await renderResponse(data);
    } else {
      setStatus("未返回几何数据");
    }
  } catch (e) {
    setStatus(`网络错误：${e.message}`);
  } finally {
    sendEl.disabled = false;
    inputEl.value = "";
  }
}

// 上传图谱 JSON 文件
const uploadBtn = document.getElementById("btn-upload");
const fileInput = document.getElementById("graph-file");
uploadBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const obj = JSON.parse(reader.result);
      sendGraph(obj, file.name);
    } catch (err) {
      setStatus(`文件不是合法 JSON：${err.message}`);
    }
    fileInput.value = ""; // 允许重复上传同一文件
  };
  reader.readAsText(file);
});

sendEl.addEventListener("click", sendCommand);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendCommand();
});
clearBtn.addEventListener("click", () => { clearSTL(); setStatus("场景已清空"); });

/* ---------------- 渲染循环 ---------------- */
function animate() {
  requestAnimationFrame(animate);
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
