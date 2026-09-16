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
  exitTour();                     // 巡游中清空场景 => 先停止巡游
  grow = null;
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
let grow = null;                       // 渐进式生长状态：{ total, start, duration }
let currentGraph = null;               // 场上场景所依据的实例图谱（后端随响应回传，游览时原样带回）
const EDGE_VERTS_PER_BOX = 24;        // 与 addBoxEdges 中 tmpl 顶点数(12条边×2点)一致

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
  // 按 Y 升序（从底向上）组织实例顺序，使渐显呈现“建筑自地面长高”的效果
  const ordered = [...boxes].sort((a, b) => a.y - b.y);
  for (let i = 0; i < ordered.length; i++) {
    const b = ordered[i];
    p.set(b.x, b.y, b.z);
    s.set(b.w * FILL, b.h * FILL, b.d * FILL);
    m.compose(p, q, s);
    voxMesh.setMatrixAt(i, m);
    col.set(b.color !== undefined ? b.color : 0x999999);
    voxMesh.setColorAt(i, col);
  }
  voxMesh.instanceMatrix.needsUpdate = true;
  if (voxMesh.instanceColor) voxMesh.instanceColor.needsUpdate = true;
  voxMesh.userData.boxes = ordered;   // 供点选反查构件名（与实例顺序一致）
  boxRoot.add(voxMesh);
  addBoxEdges(ordered);                // 叠加每个体素的边框线，凸显体素结构（同序）

  // 先按全部体素算好最终构图，相机一开始就对准（避免增长过程中镜头漂移）
  const bb = computeBoxesAABB(boxes);
  if (!bb.isEmpty()) fitCameraToBox(bb);

  // 包围球必须在这里按「全量实例」算好再缓存：
  // three 的 InstancedMesh 只用算球那一刻的 count 计算 boundingSphere，且算完永久缓存。
  // 若留给 three 在渲染时惰性计算，那时 count 已被下面的生长动画压到 0~24，
  // 球体会退化成墙角一小块（实测 r=2.8m，而正确值 r=24.9m），
  // 于是视锥剔除会把整个模型错误剔除 —— 画面只剩 voxEdges 的线框（放大后尤其明显）。
  voxMesh.computeBoundingSphere();

  // 渐进式生长：实例已按 Y 升序组织，故分帧渐显即从底向上“长高”
  // （InstancedMesh.count 控制可见实例数；边框线用 setDrawRange 同步裁剪）。
  // 匀速线性增长，便于看清“建筑自地面层层升起”的过程；总数越多耗时越长，封顶 7s。
  voxMesh.count = 0;
  if (voxEdges) voxEdges.geometry.setDrawRange(0, 0);
  const total = ordered.length;
  const duration = Math.min(7000, Math.max(3000, Math.round(total / 2)));
  grow = { total, start: performance.now(), duration };
  setStatus(`正在生成体素模型 · ${total} 体素`);
  return total;
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

function computeBoxesAABB(boxes) {
  const bb = new THREE.Box3();
  for (const b of boxes) {
    bb.expandByPoint(new THREE.Vector3(b.x - b.w / 2, b.y - b.h / 2, b.z - b.d / 2));
    bb.expandByPoint(new THREE.Vector3(b.x + b.w / 2, b.y + b.h / 2, b.z + b.d / 2));
  }
  return bb;
}

function fitCameraToBox(bb) {
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

// 兼容保留：基于场景对象计算（当前仅 addBoxes 改用 fitCameraToBox）
function fitCameraToObject(obj) {
  const bb = new THREE.Box3().setFromObject(obj);
  fitCameraToBox(bb);
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
    exitTour(); clearBoxes(); currentGraph = null; setStatus("场景已清空"); return;  }
  if (data.action === "tour") {
    // 路线由后端按「本次这张图谱」派生；前端只负责把图谱带过去，不重建模型
    if (data.graph) currentGraph = data.graph;
    if (Array.isArray(data.route) && data.route.length >= 2) tourPath = data.route;
    if (!voxMesh && Array.isArray(data.boxes)) addBoxes(data.boxes);   // 场上没模型才需要建
    enterTour();
    return;
  }
  if (Array.isArray(data.boxes)) {
    if (data.graph) currentGraph = data.graph;   // 记住场景来源，供后续游览带回
    addBoxes(data.boxes);   // 渐进式生长：状态由 addBoxes 启动、animate 在增长完成时收尾
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
  inputEl.value = "";
  if (!TOUR_WORDS.some((w) => text.includes(w))) { await postCommand({ text }); return; }
  // 游览：场上已有场景时，把「这张图谱」原样带回 —— 绝不让后端拿「游览」二字重新解析进数，
  // 否则会退化成默认进数（一进场景配三进路线，人走到空地上）。
  await postCommand(currentGraph ? { text, tour: true, graph: currentGraph } : { text, tour: true });
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
clearBtn.addEventListener("click", () => { clearBoxes(); currentGraph = null; setStatus("场景已清空"); });

/* ---------------- 游览模式：第三人称自动巡游 ---------------- */
// 方块小人沿后端派生的路线走完全院，相机吊在其后上方跟随，遇实体自动拉近。
// 路线不是前端常量：由后端「实例图谱 + ④ 几何实算坐标」实时派生随响应下发（data.route），
// 故 1/2/3/4 进自适应，不会出现「按三进写死」导致的越界或穿不存在的门。
// 每个路径点的 y = 落脚面高度（院面 0 / 台基 0.30）。

const WALK_SPEED = 1.55;      // 步行速度 m/s
const CAM_BACK   = 3.60;      // 相机在小人后方的水平距离
const CAM_UP     = 2.00;      // 相机离地高度
const CAM_ANCHOR = 1.30;      // 视线锚点（小人胸肩）高度
const TURN_K     = 6.00;      // 转向平滑系数
const CAM_BOOM   = Math.hypot(CAM_BACK, CAM_UP - CAM_ANCHOR);  // 吊臂全长（锚点→理想机位）
const CAM_TURN_MAX = 2.4;     // 相机吊臂最大角速度 rad/s（≈137°/s），限制急转时的扫镜速率

// 游览意图判定属 UI 语义，此表是唯一来源；后端只认 body.tour 标记，不重复维护关键词表
const TOUR_WORDS = ["游览", "浏览", "参观", "观光", "逛"];

let tourPath = [];            // 本轮巡游使用的路线（由 data.route 填充）

/* 方块小人：Minecraft 风格六件套（头/发/躯干/双臂/双腿），肢体以关节为轴心便于摆动 */
function makeTourist() {
  const root = new THREE.Group();
  const M = (c) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.9, metalness: 0 });
  const B = (w, h, d, c) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), M(c));

  const torso = B(0.46, 0.62, 0.26, 0x2f9e93);      // 上衣
  torso.position.y = 1.01;                          // 躯干 0.70 ~ 1.32
  root.add(torso);

  const head = B(0.42, 0.38, 0.42, 0xe3b98d);       // 头 1.32 ~ 1.70
  head.position.y = 1.51;
  root.add(head);

  const hair = B(0.45, 0.09, 0.45, 0x3f2f24);       // 发顶 1.66 ~ 1.75
  hair.position.y = 1.705;
  root.add(hair);

  const limb = (w, h, d, c, px, py) => {            // 关节在 (px,py)，肢体向下垂 h
    const pivot = new THREE.Group();
    pivot.position.set(px, py, 0);
    const m = B(w, h, d, c);
    m.position.y = -h / 2;
    pivot.add(m);
    root.add(pivot);
    return pivot;
  };

  const legL = limb(0.17, 0.70, 0.17, 0x3d4a8f, -0.12, 0.70);
  const legR = limb(0.17, 0.70, 0.17, 0x3d4a8f,  0.12, 0.70);
  const armL = limb(0.15, 0.60, 0.15, 0x2f9e93, -0.31, 1.30);
  const armR = limb(0.15, 0.60, 0.15, 0x2f9e93,  0.31, 1.30);

  root.userData.limbs = { legL, legR, armL, armR };
  root.visible = false;
  return root;
}

const tourist = makeTourist();
scene.add(tourist);

/* 相机避障用的粗占据格（0.5m）——只标记"高于台基"的实体，台基不挡相机视线 */
const OCC_CELL = 0.5;
let occ = null;

function buildOccupancy(boxes) {
  occ = null;
  if (!boxes || !boxes.length) return;
  const bb = computeBoxesAABB(boxes);
  if (bb.isEmpty()) return;
  const ox = Math.floor(bb.min.x / OCC_CELL) - 1;
  const oz = Math.floor(bb.min.z / OCC_CELL) - 1;
  const nx = Math.ceil(bb.max.x / OCC_CELL) - ox + 2;
  const ny = Math.ceil((bb.max.y + 1.5) / OCC_CELL) + 2;
  const nz = Math.ceil(bb.max.z / OCC_CELL) - oz + 2;
  const g = new Uint8Array(nx * ny * nz);
  const Y0 = 0.45, Y1 = 3.40;
  for (const b of boxes) {
    const y0 = b.y - b.h / 2, y1 = b.y + b.h / 2;
    if (y1 <= Y0 || y0 >= Y1) continue;
    const i0 = Math.floor((b.x - b.w / 2) / OCC_CELL) - ox, i1 = Math.floor((b.x + b.w / 2) / OCC_CELL) - ox;
    const j0 = Math.floor((b.z - b.d / 2) / OCC_CELL) - oz, j1 = Math.floor((b.z + b.d / 2) / OCC_CELL) - oz;
    const k0 = Math.max(0, Math.floor(y0 / OCC_CELL)), k1 = Math.min(ny - 1, Math.floor(y1 / OCC_CELL));
    for (let k = k0; k <= k1; k++)
      for (let i = Math.max(0, i0); i <= Math.min(nx - 1, i1); i++)
        for (let j = Math.max(0, j0); j <= Math.min(nz - 1, j1); j++)
          g[(k * nz + j) * nx + i] = 1;
  }
  occ = { g, ox, oz, nx, ny, nz };
}

function occAt(x, y, z) {
  if (!occ) return false;
  const i = Math.floor(x / OCC_CELL) - occ.ox;
  const j = Math.floor(z / OCC_CELL) - occ.oz;
  const k = Math.floor(y / OCC_CELL);
  if (i < 0 || i >= occ.nx || j < 0 || j >= occ.nz || k < 0 || k >= occ.ny) return false;
  return occ.g[(k * occ.nz + j) * occ.nx + i] === 1;
}

// camYaw = 相机吊臂方向，独立于人物 yaw 且更慢，用来消除急转时的镜头猛甩
const tour = { active: false, i: 0, t: 0, pauseLeft: 0, yaw: 0, camYaw: 0, camDist: 0, phase: 0 };
const tourLabelEl = document.getElementById("tour-label");
const exitTourBtn = document.getElementById("btn-exit-tour");

function lerpAngle(a, b, t) {           // 角度插值，处理 ±π 跨越
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

function finishGrow() {                 // 进游览前把"生长动画"一次性收尾，避免等待
  if (grow && voxMesh) {
    voxMesh.count = grow.total;
    if (voxEdges) voxEdges.geometry.setDrawRange(0, grow.total * EDGE_VERTS_PER_BOX);
    grow = null;
  }
}

function enterTour() {
  if (!voxMesh) { setStatus("先生成一座院子，再输入「开始游览」"); return; }
  if (!tourPath || tourPath.length < 2) { setStatus("未取到巡游路线，请重新生成院落"); return; }
  finishGrow();
  buildOccupancy(voxMesh.userData.boxes);

  const p0 = tourPath[0], p1 = tourPath[1];
  tour.active = true; tour.i = 0; tour.t = 0; tour.phase = 0;
  tour.pauseLeft = p0.pause || 0;
  tour.yaw = Math.atan2(p1.x - p0.x, p1.z - p0.z);
  tour.camYaw = tour.yaw;
  tour.camDist = CAM_BOOM;

  tourist.visible = true;
  tourist.position.set(p0.x, p0.y, p0.z);
  tourist.rotation.y = tour.yaw;
  camera.position.set(
    p0.x - Math.sin(tour.yaw) * CAM_BACK,
    p0.y + CAM_UP,
    p0.z - Math.cos(tour.yaw) * CAM_BACK
  );
  controls.enabled = false;             // 与观察模式互斥
  document.body.classList.add("touring");
  if (tourLabelEl) tourLabelEl.textContent = p0.label || "";
  setStatus("游览中 · 沿中轴自南向北", true);
}

function exitTour() {
  if (!tour.active) return;
  tour.active = false;
  tourist.visible = false;
  controls.enabled = true;
  document.body.classList.remove("touring");
  if (voxMesh && voxMesh.userData.boxes) fitCameraToBox(computeBoxesAABB(voxMesh.userData.boxes));
  setStatus("已退出游览");
}

/* 相机跟随（第三人称吊臂）。三个关键点，逐一对应此前实测到的穿墙/抖动：
   ① 吊臂方向用独立的 camYaw（比人物 TURN_K 更慢），拐角时镜头平滑扫过而非随人猛甩；
   ② 沿吊臂向外逐格采样求「最远空位」dTgt，相机距离只在 [0, dTgt] 内平滑 —— 位置恒落在
      无遮挡段内，因此任何一帧都不可能落在实体里（旧版把 back 硬夹到 0.5，等于在墙里
      强行摆一台相机，实测入墙 33~269 帧、内院连续 70 帧）；
   ③ 距离"收快放慢"，且硬夹不超过 dTgt：进门洞时不至于弹来弹去，沿墙走时也不会抖。 */
function applyTourCamera(dt) {
  // 吊臂转向：指数跟随 + 角速度上限。若只做指数跟随，yaw 突变时吊臂会一帧扫过大角度，
  // 使「最远空位」dTgt 骤降、被硬夹成一帧 3m 级硬切（实测末点回望处 3.21m）。
  // 限速后 dTgt 逐帧缓变，收镜变成连续的一段而非一刀。
  const want = lerpAngle(tour.camYaw, tour.yaw, 1 - Math.exp(-4.5 * dt));
  const cap = CAM_TURN_MAX * dt;
  tour.camYaw += Math.max(-cap, Math.min(cap, want - tour.camYaw));

  const p = tourist.position;
  const fx = Math.sin(tour.camYaw), fz = Math.cos(tour.camYaw);
  const ax = p.x, ay = p.y + CAM_ANCHOR, az = p.z;                       // 视线锚点
  const rise = CAM_UP - CAM_ANCHOR;

  let t = 0;                                                             // 最远空位比例
  const N = 16;
  for (let s = 1; s <= N; s++) {
    const k = s / N;
    if (occAt(ax - fx * CAM_BACK * k, ay + rise * k, az - fz * CAM_BACK * k)) break;
    t = k;
  }
  const dTgt = t * CAM_BOOM;                                             // 目标机位距锚点

  const kPull = dTgt < tour.camDist ? (1 - Math.exp(-18 * dt))           // 收：快
                                    : (1 - Math.exp(-6 * dt));           // 放：慢
  tour.camDist += (dTgt - tour.camDist) * kPull;
  if (tour.camDist > dTgt) tour.camDist = dTgt;                          // 绝不越过遮挡面
  if (tour.camDist < 0) tour.camDist = 0;

  const u = tour.camDist / CAM_BOOM;
  camera.position.set(ax - fx * CAM_BACK * u, ay + rise * u, az - fz * CAM_BACK * u);
  tourist.visible = tour.camDist > 1.05;                                 // 贴太近时藏起人物
  camera.lookAt(ax + fx * 1.3, ay + 0.12, az + fz * 1.3);
}

function updateTour(dt) {
  const path = tourPath;
  const last = path[path.length - 1];

  if (tour.i >= path.length - 1) {                              // 末点：留驻并回望
    if (last.look) {
      tour.yaw = lerpAngle(tour.yaw, Math.atan2(last.look[0] - last.x, last.look[1] - last.z),
                           1 - Math.exp(-TURN_K * dt));
    }
    tourist.rotation.y = tour.yaw;
    return applyTourCamera(dt);
  }

  let a = path[tour.i], b = path[tour.i + 1];

  if (tour.pauseLeft > 0) {                                     // 驻足：转头看点
    tour.pauseLeft -= dt;
    if (a.look) {
      tour.yaw = lerpAngle(tour.yaw, Math.atan2(a.look[0] - a.x, a.look[1] - a.z),
                           1 - Math.exp(-TURN_K * dt));
    }
    tour.phase *= Math.exp(-9 * dt);                            // 收步
  } else {
    const segLen = Math.max(Math.hypot(b.x - a.x, b.z - a.z), 1e-6);
    const speed = Math.abs(b.y - a.y) > 0.01 ? WALK_SPEED * 0.75 : WALK_SPEED;  // 上下台阶略慢
    tour.t += (speed * dt) / segLen;
    // 到站即推进下标、并把段内进度按整段折算(t-=1)；
    // 修：此前 i++ 后仍拿「旧的 a/b + t=0」算位置，等于每过一个路径点把小人打回整段起点
    // （实测 5.99m 回跳，正好是「折向中轴」那段长度）。跨段后必须重取 a/b 再算位置。
    while (tour.t >= 1 && tour.i < path.length - 1) {
      tour.t -= 1;
      tour.i += 1;
      const np = path[tour.i];
      tour.pauseLeft = np.pause || 0;
      // 过渡点（坐标层，无站名）不清空站名，沿用上一站，避免标签闪断
      if (tourLabelEl && np.label) tourLabelEl.textContent = np.label;
      if (tour.i >= path.length - 1 || tour.pauseLeft > 0) { tour.t = 0; break; }
    }
    if (tour.i >= path.length - 1) {                            // 已抵达末点：交给末点分支
      const e = path[path.length - 1];
      tourist.position.set(e.x, e.y, e.z);
      tourist.rotation.y = tour.yaw;
      return applyTourCamera(dt);
    }
    a = path[tour.i]; b = path[tour.i + 1];
    tourist.position.set(
      a.x + (b.x - a.x) * tour.t,
      a.y + (b.y - a.y) * tour.t,
      a.z + (b.z - a.z) * tour.t
    );
    tour.yaw = lerpAngle(tour.yaw, Math.atan2(b.x - a.x, b.z - a.z), 1 - Math.exp(-TURN_K * dt));
    tour.phase += (speed * dt) / 0.34;                          // 步频
  }

  tourist.rotation.y = tour.yaw;
  const sw = Math.sin(tour.phase) * 0.52;
  const L = tourist.userData.limbs;
  L.legL.rotation.x = sw;      L.legR.rotation.x = -sw;
  L.armL.rotation.x = -sw * 0.85; L.armR.rotation.x = sw * 0.85;

  applyTourCamera(dt);
}

if (exitTourBtn) exitTourBtn.addEventListener("click", exitTour);
addEventListener("keydown", (e) => { if (e.key === "Escape" && tour.active) exitTour(); });

/* ---------------- 渲染循环 ---------------- */
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

let lastFrameT = performance.now();
function animate() {
  requestAnimationFrame(animate);
  const now = performance.now();
  const dt = Math.min(0.05, (now - lastFrameT) / 1000);
  lastFrameT = now;

  grid.position.x = Math.round(modelCenter.x);
  grid.position.z = Math.round(modelCenter.z);

  if (tour.active) {
    updateTour(dt);                 // 游览模式：相机由巡游驱动，OrbitControls 让位
  } else {
    controls.update();
  }

  if (grow && voxMesh) {
    const t = Math.min(1, (performance.now() - grow.start) / grow.duration);
    const eased = t;                                // 匀速线性，便于看清生长过程
    const target = Math.min(grow.total, Math.floor(grow.total * eased));
    if (target !== voxMesh.count) {
      voxMesh.count = target;
      if (voxEdges) voxEdges.geometry.setDrawRange(0, target * EDGE_VERTS_PER_BOX);
    }
    if (t >= 1) {
      voxMesh.count = grow.total;
      if (voxEdges) voxEdges.geometry.setDrawRange(0, grow.total * EDGE_VERTS_PER_BOX);
      const n = grow.total;
      grow = null;
      setStatus(`已生成体素模型 · ${n} 体素`);
    }
  }
  renderer.render(scene, camera);
}
animate();
