/* BUILDING.WIKI · MVP 2.0 前端
 *
 * 链路（全 Agent 形态，2026-09-22）：文本 → ACP(OAK Agent)
 *       Agent 侧一气呵成：推导骨架 → 装配实例图谱 → 上传云存储(cos:<key>)
 *       → 调 MCP generate_building(按引用读回 → ④ compute_geometry → ⑤ geometry_to_boxes)
 *       → 返回体素 BOX 清单 → 前端只负责渲染。
 *
 * 为什么传引用不传值：实例图谱 ~10KB 若走工具入参通道会被 harness 截断损坏，
 * 故 Agent 先上传拿 cos: 引用、再让 generate_building 按引用读回，绕开 10KB 通道。
 * 体素结果可能较大（~0.5–1MB），harness 可能落盘为 <persisted-output> 引用，
 * 前端据此拉取（具体格式以 item5 运行时实测为准，本文件已做兼容分支）。
 *
 * 分层纪律：本文件只管「取数 + 画」。拓扑/规制在 Agent 侧 skill，
 * 坐标/几何/体素化在容器内引擎与 MCP，前端不重复任何一方的推导。
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const CFG = window.BW_CONFIG || {};
const ACP_URL = CFG.ACP_URL;
const KEY = (CFG.PUBLISHABLE_KEY || "").trim();

/* ================= 场景基础 ================= */
const container = document.getElementById("scene-container");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf4f5f7);
scene.fog = new THREE.Fog(0xf4f5f7, 60, 160);

const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 500);
// 默认从正南、略高处俯视正面（大门所在的南立面最近、落在屏幕下方）；
// 配合体素 X 取负，大门(东南角)稳定显示在屏幕右下，与「面南看、大门在右手边」一致。
camera.position.set(0, 38, -55);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
container.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xffffff, 0.8));
const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
dirLight.position.set(20, 40, 15);
scene.add(dirLight);

const grid = new THREE.GridHelper(1000, 1000, 0xb9c1cd, 0xdfe3ea);
grid.position.y = -0.01;
scene.add(grid);
const modelCenter = new THREE.Vector3();

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 8;
controls.maxDistance = 200;
controls.target.set(0, 0, 0);

/* ============ 材质：每类(role)随手分一张贴图 ============
   贴图是 16×16 的**灰度**图案（亮度均值贴近 255），与 role 颜色（instanceColor）
   **相乘**上色 —— 图案负责"方块感"，颜色负责"这是哪一栋"，互不干扰。
   这正是 Minecraft 的做法：几何严丝合缝，方块感来自贴图本身。

   role -> 贴图**不带业务含义**：按 role 名做确定性哈希取模，落到 4 张里的一张。
   确定性是硬要求 —— 不能用 Math.random()，否则同一座院每次生成换个花纹、像坏了；
   哈希保证「同一类每次长一样」，且前端不需要任何知识表或接口。 */
const TEXTURES = ["zhuan", "qiang", "mu", "hui"];

function textureOfRole(role) {
  const s = String(role || "");
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return TEXTURES[h % TEXTURES.length];
}

const texLoader = new THREE.TextureLoader();
const texCache = new Map();
function loadTexture(name) {
  let t = texCache.get(name);
  if (!t) {
    t = texLoader.load(`./textures/${name}.png`);
    t.colorSpace = THREE.SRGBColorSpace;
    t.magFilter = THREE.NearestFilter;              // 放大用最近邻，保住像素块感
    t.minFilter = THREE.NearestMipmapNearestFilter;
    t.anisotropy = 4;
    texCache.set(name, t);
  }
  return t;
}

/* ================= 体素 ================= */
const boxRoot = new THREE.Group();
scene.add(boxRoot);

let voxMeshes = [];    // 按贴图分组的 InstancedMesh（贴图不同，材质不能共用）
let voxBoxes = [];     // Y 升序，供点选反查与取景
let grow = null;       // 渐进生长：{ total, start, duration, ys, parts }

function clearBoxes() {
  grow = null;
  for (const mesh of voxMeshes) {          // 各组共用同一份 BoxGeometry，几何体只释一次
    boxRoot.remove(mesh);
    mesh.material.dispose();               // 贴图在 texCache 里复用，不随组销毁
  }
  if (voxMeshes.length) voxMeshes[0].geometry.dispose();
  voxMeshes = [];
  voxBoxes = [];
}

function addBoxes(boxes) {
  clearBoxes();
  if (!Array.isArray(boxes) || !boxes.length) return 0;

  // 按贴图分组，每组一个 InstancedMesh（贴图不同，材质不能共用）
  const groups = new Map();
  for (const b of boxes) {
    const tex = textureOfRole(b.role);
    let arr = groups.get(tex);
    if (!arr) groups.set(tex, (arr = []));
    arr.push(b);
  }

  const geo = new THREE.BoxGeometry(1, 1, 1);   // 各组共用一份几何体（UV 每面 0→1，即每面一张贴图）
  const m = new THREE.Matrix4();
  const p = new THREE.Vector3();
  const q = new THREE.Quaternion();
  const s = new THREE.Vector3();
  const col = new THREE.Color();
  const parts = [];
  let total = 0;

  for (const [tex, arr] of groups) {
    // 组内 Y 升序 → 「低于阈值的高度全显示」即整体自下而上长高
    const sorted = arr.slice().sort((a, b) => a.y - b.y);
    const mat = new THREE.MeshStandardMaterial({
      map: loadTexture(tex),
      roughness: 0.82,
      metalness: 0.0,                  // 砖木石都不用金属感，免得高光糊住贴图
    });
    const mesh = new THREE.InstancedMesh(geo, mat, sorted.length);
    for (let i = 0; i < sorted.length; i++) {
      const b = sorted[i];
      // 显示层 X 取负：引擎约定「东端=east-end → +X」，但在 Y 轴朝上的标准 3D 视角下，
      // 从正面(南)看时 +X 会落到左手边(西)。取负后引擎的「东端」显示为面向正面时的右手边(东)，
      // 符合「面南而立、大门在东南角」的直觉。仅显示镜像，引擎/知识包坐标语义不变。
      p.set(-b.x, b.y, b.z);
      s.set(b.w, b.h, b.d);            // 满格：相邻块共面 → 零缝
      m.compose(p, q, s);
      mesh.setMatrixAt(i, m);
      col.set(b.color !== undefined ? b.color : 0x999999);
      mesh.setColorAt(i, col);
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.userData.boxes = sorted;      // 点选反查（下标与实例一致）

    // 包围球必须在 count 归零前算好：three 只用「算球那一刻的 count」，
    // 算完永久缓存；若留给渲染时惰性计算，那时 count 已被生长动画压到很小，
    // 球体会退化到墙角一小块，视锥剔除会把整个模型剔掉（画面空场景）。
    mesh.computeBoundingSphere();
    mesh.count = 0;

    boxRoot.add(mesh);
    voxMeshes.push(mesh);
    parts.push({ mesh, ys: sorted.map((b) => b.y) });
    total += sorted.length;
  }

  voxBoxes = boxes.slice().sort((a, b) => a.y - b.y);

  const bb = computeBoxesAABB(boxes);
  if (!bb.isEmpty()) fitCameraToBox(bb);   // 先按全量构图对准相机，避免生长中镜头漂移

  const duration = Math.min(7000, Math.max(3000, Math.round(total / 2)));
  grow = { total, start: performance.now(), duration, ys: voxBoxes.map((b) => b.y), parts };
  setStatus(`生成体素模型 · ${total} 体素`);
  return total;
}

function growTo(threshold) {
  if (!grow) return;
  for (const part of grow.parts) {         // 各组按同一高度阈值推进，整体仍是自下而上长高
    const ys = part.ys;
    let n = 0;
    while (n < ys.length && ys[n] <= threshold) n++;
    if (part.mesh.count !== n) part.mesh.count = n;
  }
}

function finishGrow() {
  if (!grow) return;
  for (const part of grow.parts) part.mesh.count = part.ys.length;
  grow = null;
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
  camera.near = Math.max(dist / 1000, 0.01);
  camera.far = dist * 20;
  camera.updateProjectionMatrix();
  grid.position.y = bb.min.y - 0.01;
  scene.fog.near = dist * 0.8;
  scene.fog.far = dist * 4;
}

/* ================= 点选看构件名 ================= */
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downXY = null;

renderer.domElement.addEventListener("pointerdown", (e) => {
  downXY = [e.clientX, e.clientY];
});
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!downXY) return;
  const moved = Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]);
  downXY = null;
  if (moved > 5) return;               // 拖拽不算点选
  if (!voxMeshes.length) return;
  pointer.x = (e.clientX / innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(voxMeshes, false);  // 命中哪组，就用哪组的实例表反查
  if (hits.length) {
    const hit = hits[0];
    const b = hit.object.userData.boxes[hit.instanceId];
    if (b) setStatus(`选中：${b.label || b.role || "未知"}`);
  }
});

/* ================= ACP：调 Agent，读事件流 ================= */
function toolLabel(title) {
  if (!title) return "工具";
  if (title.includes("generate_building")) return "生成体素模型";
  if (title === "Read") return "读知识库";
  if (title === "Write") return "写中间文件";
  if (title === "Bash") return "跑装配脚本";
  return title.replace(/^mcp__[^_]+__/, "");
}

/* 方案 B（2026-09-29）：generate_building 现回传 JSON
 *   {"boxes_ref": "<预签名URL 或 内联数组>", "instance_ref": "cos:instances/<uuid>.json"}
 * boxes_ref 是 URL 时走 fetch；是数组时（BW_BOXES_INLINE）直接渲染。
 * instance_ref 是下一次「增量/局部编辑」所需的实例图谱引用，回灌给前端持有。 */
function harvestGenBuilding(raw) {
  if (typeof raw !== "string" || raw.length < 2) return {};
  let text = raw.split("\n").map((l) => l.replace(/^\s*\d+\t/, "")).join("\n").trim();
  const persisted = raw.match(/<persisted-output>([\s\S]*?)<\/persisted-output>/i);
  if (persisted) text = persisted[1].trim();
  let obj = null;
  try { obj = JSON.parse(text); } catch { /* 非 JSON */ }
  if (!obj) return {};
  if (Array.isArray(obj)) return { boxes: obj };                 // 极旧形态：直接是数组
  // harness 可能包若干层 {result: "<json 串>"}；逐层下钻直到见到 boxes_ref。
  // （旧实现只在首次 JSON.parse 失败时才拆 result 层，但外层往往能解析成功，
  //   于是永远进不到兼容分支 → 明明有 boxes_ref 却返回 {}。）
  for (let i = 0; i < 4 && obj && typeof obj === "object"; i++) {
    if (obj.boxes_ref !== undefined || obj.boxes !== undefined) break;
    if (typeof obj.result === "string") {
      try { obj = JSON.parse(obj.result); continue; } catch { break; }
    }
    if (typeof obj.result === "object" && obj.result) { obj = obj.result; continue; }
    break;
  }
  if (!obj || typeof obj !== "object") {
    return typeof obj === "string" ? { boxes: obj } : {};        // 旧形态：裸 URL 串
  }
  if (obj.boxes_ref !== undefined) {
    return {
      boxes: obj.boxes_ref,                       // URL 字符串 或 数组
      instanceRef: obj.instance_ref || null,
    };
  }
  if (obj.boxes !== undefined) return { boxes: obj.boxes, instanceRef: obj.instance_ref || null };
  return {};
}

function handleFrame(frame, titles, state, onEvent) {
  const upd = (frame.params || {}).update || {};
  const t = upd.sessionUpdate;

  if (t === "agent_message_chunk") {
    const tx = (upd.content || {}).text;
    if (tx) { state.text += tx; onEvent({ type: "text", text: state.text }); }
    return;
  }

  if (t === "tool_call") {
    if (upd.toolCallId) titles.set(upd.toolCallId, upd.title || "");
    state.tools++;
    onEvent({ type: "tool", label: toolLabel(upd.title), phase: "start" });
    return;
  }

  if (t === "tool_call_update") {
    const name = titles.get(upd.toolCallId) || "";
    if (upd.status === "failed") {
      state.failed++;
      onEvent({ type: "tool", label: toolLabel(name), phase: "failed" });
      return;
    }
    if (upd.status !== "completed") return;
    onEvent({ type: "tool", label: toolLabel(name), phase: "done" });

    // 全 Agent 形态：Agent 调 generate_building 算完 ④⑤，BOX + instance 引用经 rawOutput 回流
    if (upd.rawOutput && name.includes("generate_building")) {
      const r = harvestGenBuilding(upd.rawOutput);
      if (r.boxes) state.boxes = r.boxes;                 // 末次成功的（array 或 ref 字符串）
      if (r.instanceRef) state.instanceRef = r.instanceRef; // 方案 B：下一次编辑的引用
    }
  }
}

async function runAgent(text, onEvent) {
  const resp = await fetch(ACP_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
      "Authorization": "Bearer " + KEY,
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "session/prompt",
      params: { prompt: [{ type: "text", text }] },
    }),
  });
  if (!resp.ok || !resp.body) throw new Error(`Agent 网关返回 HTTP ${resp.status}`);

  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  const titles = new Map();
  const state = { text: "", boxes: null, instanceRef: null, tools: 0, failed: 0 };
  let buf = "";
  let stop = false;

  while (!stop) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).replace(/\r$/, "");
      buf = buf.slice(nl + 1);
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") { stop = true; break; }
      let frame;
      try { frame = JSON.parse(payload); } catch { continue; }
      handleFrame(frame, titles, state, onEvent);
    }
  }
  return state;
}

/* ================= UI ================= */
const inputEl = document.getElementById("cmd-input");
const sendEl = document.getElementById("cmd-send");
const statusEl = document.getElementById("hud-status");
const clearBtn = document.getElementById("btn-clear");
const chatBody = document.getElementById("chat-body");
const chatPanel = document.getElementById("chat-panel");
const chatToggle = document.getElementById("btn-chat-toggle");

let statusTimer = null;
function setStatus(msg, busy = false) {
  // busy 时保留「阶段说明 + 计时」子元素；非 busy 时走纯文本（textContent 会清掉子元素）
  if (busy) {
    statusEl.innerHTML = "";
    statusEl.appendChild(document.createTextNode(msg || ""));
    if (stageHintText) {
      const hint = document.createElement("span");
      hint.className = "stage-hint";
      hint.textContent = stageHintText;
      statusEl.appendChild(hint);
    }
  } else {
    statusEl.textContent = msg || "";
  }
  statusEl.classList.toggle("busy", busy);
  statusEl.classList.remove("hidden");
  clearTimeout(statusTimer);
  if (!busy) statusTimer = setTimeout(() => statusEl.classList.add("hidden"), 2600);
}

/* ── 阶段提示 + 计时器 ──────────────────────────────────────────────
   一轮「新建」典型要 30~60s（其中 LLM 推理占绝大部分，④⑤ 引擎本身 <1s）。
   只显示单个工具名时用户不知道还要等多久，故补：当前阶段说明 + 已耗时秒数。
   ▸ 阶段说明按已完成的工具推进，用户始终知道"卡在哪一步"。 */
let stageHintText = "";
let stageCurrent = "";
let stageT0 = 0;
let stageTimer = null;

// 各工具对应的人话阶段（toolLabel 已做工具名→中文，这里补"在干什么"）
const STAGE_HINT = {
  "读知识库": "正在读古建规制知识库",
  "跑装配脚本": "正在装配实例图谱",
  "写中间文件": "正在准备骨架",
  "生成体素模型": "正在算几何、生成三维体素",
};

function startStageTimer() {
  stageT0 = Date.now();
  clearInterval(stageTimer);
  stageTimer = setInterval(() => {
    if (!stageHintText) return;
    const s = Math.floor((Date.now() - stageT0) / 1000);
    setStatus(stageCurrent || "处理中", true);
    if (stageHintText.indexOf("·") < 0) {
      stageHintText = (STAGE_HINT[stageCurrent] || stageHintText) + " · " + s + "s";
    } else {
      stageHintText = stageHintText.replace(/· \d+s$/, "· " + s + "s");
    }
  }, 1000);
}

function stopStageTimer() {
  clearInterval(stageTimer);
  stageTimer = null;
  stageHintText = "";
}

let agentMsgEl = null;
function clearChat() { chatBody.innerHTML = ""; agentMsgEl = null; }

function appendChat(who, text) {
  const el = document.createElement("div");
  el.className = "msg msg-" + who;
  el.textContent = text;
  chatBody.appendChild(el);
  chatBody.scrollTop = chatBody.scrollHeight;
  return el;
}

function updateAgentChat(text) {
  if (!agentMsgEl) agentMsgEl = appendChat("agent", "");
  agentMsgEl.textContent = text;
  chatBody.scrollTop = chatBody.scrollHeight;
}

chatToggle.addEventListener("click", () => {
  const collapsed = chatPanel.classList.toggle("collapsed");
  chatToggle.textContent = collapsed ? "展开" : "收起";
});

/* ================= 主流程 ================= */
// 方案 B（2026-09-29）：实例图谱为真相源，前端持有当前模型的实例引用，
// 编辑时回灌给 Agent（让它 --instance 该引用做增量/局部修改），
// 跑完用新回传的 instance_ref 更新本变量 —— 实现渐进式持续编辑。
let currentInstanceRef = null;

// 用户明确要「新建/重做」时，不回灌旧引用、并清空当前引用（回到新建分支）。
function isNewBuildIntent(text) {
  return /新建|新盖|再盖|重做|重新生成|推倒|从头|另(来|建|做)|换一个/.test(text);
}

// 方案 B：已有当前实例时，把引用装进 prompt，提示 Agent 走「编辑」而非「重建」。
function buildPrompt(text) {
  if (currentInstanceRef && !isNewBuildIntent(text)) {
    return `[当前实例图谱引用] ${currentInstanceRef}\n`
      + `（若需在该模型上增量/局部修改，请以上述引用为 --instance 调用 assemble.mjs 编辑，不要重建；`
      + `否则按用户意图新建。）\n${text}`;
  }
  return text;
}

let busy = false;

function onAgentEvent(ev) {
  if (ev.type === "text") { updateAgentChat(ev.text); return; }
  if (ev.type === "tool") {
    const mark = ev.phase === "failed" ? "✗" : ev.phase === "done" ? "✓" : "…";
    // 阶段说明：工具开始时切换，结束/失败时保持最后一次（直到下一个工具）
    if (ev.phase === "start") {
      stageCurrent = ev.label;
      stageHintText = STAGE_HINT[ev.label] || ev.label;
    }
    setStatus(`${mark} ${ev.label}`, true);
  }
}

async function send() {
  if (busy) return;
  const text = inputEl.value.trim();
  if (!text) return;
  if (!KEY) {
    setStatus("缺少 Publishable Key —— 请在 web/config.local.js 填入");
    chatPanel.classList.remove("collapsed");
    chatToggle.textContent = "收起";
    appendChat("agent", "缺少 Publishable Key。\n\n请复制 web/config.example.js 为 web/config.local.js，填入 Publishable Key 后刷新页面。");
    return;
  }

  inputEl.value = "";
  busy = true;
  sendEl.disabled = true;
  clearChat();
  chatPanel.classList.remove("collapsed");
  chatToggle.textContent = "收起";
  appendChat("user", text);
  stageCurrent = "推导骨架";
  stageHintText = "正在理解需求、匹配规制";
  setStatus("Agent 正在推导骨架…", true);
  startStageTimer();

  // 方案 B（2026-09-29）：编辑时把当前实例引用回灌给 Agent，让其基于现有实例做增量/局部修改；
  // 用户显式「新建/重做」则清空引用，走新建分支。
  if (isNewBuildIntent(text)) currentInstanceRef = null;
  const promptText = buildPrompt(text);

  try {
    const state = await runAgent(promptText, onAgentEvent);
    if (state.text) updateAgentChat(state.text);

    // 方案 B：回收本次产出的实例引用，供下次增量/局部编辑闭环（闭环关键一步）。
    if (state.instanceRef) currentInstanceRef = state.instanceRef;

    // 全 Agent 形态：体素 BOX 已在 Agent 侧由 generate_building 算出，经 ACP 流回
    // （inline 数组，或被 harness 落盘为 <persisted-output> 引用字符串）。
    let boxes = null;
    if (Array.isArray(state.boxes)) {
      boxes = state.boxes;
    } else if (typeof state.boxes === "string") {
      setStatus("体素结果较大，正在拉取…", true);
      const txt = await (await fetch(state.boxes)).text();
      boxes = JSON.parse(txt);
    }

    if (!boxes) {
      setStatus("Agent 未产出体素模型，请重试或换个说法");
      appendChat("agent", (state.text ? "\n\n" : "") +
        "（本次未取到体素结果：Agent 可能已生成成功，但前端没解析到工具返回值。若反复出现，请把控制台报错发我。）");
      return;
    }

    const n = addBoxes(boxes);
    setStatus(`已生成 · ${n} 体素`);
  } catch (e) {
    setStatus(`出错：${e.message}`);
    appendChat("agent", "（出错：" + e.message + "）");
  } finally {
    stopStageTimer();
    busy = false;
    sendEl.disabled = false;
  }
}

sendEl.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
clearBtn.addEventListener("click", () => { clearBoxes(); setStatus("场景已清空"); });

/* ================= 渲染循环 ================= */
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
  controls.update();

  if (grow) {
    const t = Math.min(1, (now - grow.start) / grow.duration);
    const target = Math.min(grow.total, Math.floor(grow.total * t));
    growTo(target > 0 ? grow.ys[target - 1] : -Infinity);
    if (t >= 1) {
      const n = grow.total;
      finishGrow();
      setStatus(`已生成体素模型 · ${n} 体素`);
    }
  }
  renderer.render(scene, camera);
}
animate();

if (!KEY) setStatus("缺少 Publishable Key —— 见 web/config.local.js");

/* ================= 本地调试模式（旁路云端 Agent） =================
   URL 带 ?local[=路径] 时，页面加载即直接 fetch 该 boxes.json 并渲染，
   完全不经过 ACP/OAK Agent —— 用于本地打磨 ④⑤ 几何（院落平面等）。
   路径解析：缺省 "./boxes.json"；以 "/" 开头 = 站点根绝对路径；
   其余按相对当前页面处理。配合：
     python tools/preview/gen_boxes.py --instance <实例>
   在仓库根目录起 http.server 使用。 */
(function localDebug() {
  const m = new URLSearchParams(location.search).get("local");
  if (m === null) return;
  const url = m === "" ? "./boxes.json" : m;
  setStatus("本地调试模式 · 读取 " + url, true);
  fetch(url)
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((boxes) => { const n = addBoxes(boxes); setStatus("已加载本地体素 · " + n + " 体素"); })
    .catch((e) => setStatus("本地读取失败：" + e.message));
})();
