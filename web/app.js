/* BUILDING.WIKI · MVP 2.0 前端
 *
 * 链路（v3，2026-09-22）：文本 → ACP(OAK Agent 推导骨架 → 装配出实例图谱)
 *       → 前端从事件流里捞出实例图谱 → 前端直连 MCP 跑 ④⑤ → Three.js 渲染
 *
 * 为什么 ④⑤ 都由前端跑、不再让 Agent 调：
 *   OAK harness 的**工具入参**通道扛不住大 payload。实测 Agent 调 compute_geometry 时，
 *   约 10KB 的实例图谱入参会先坏（变成 list，或非法 JSON 串），pydantic 直接报
 *   dict_type，它便反复重试 —— 一轮被拖到 5 分钟以上（4 次调用里 3 次失败）。
 *   而同样 ~10KB 的内容走**工具输出**通道完好无损（Agent 读 instance.json 的
 *   rawOutput 完整留在流里），浏览器直连 MCP 更是完全不经 harness。
 *   故 ④⑤ 一律由前端做，Agent 的职责收在「装配出实例图谱并打印出来」为止。
 *
 * 分层纪律：本文件只管「取数 + 画」。拓扑/规制在 Agent 侧的 skill，
 * 坐标/几何在容器内的引擎，前端不重复任何一方的推导。
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const CFG = window.BW_CONFIG || {};
const ACP_URL = CFG.ACP_URL;
const MCP_URL = CFG.MCP_URL;
const KEY = (CFG.PUBLISHABLE_KEY || "").trim();

/* ================= 场景基础 ================= */
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
controls.target.set(0, 0.5, 0);

/* ================= 体素 ================= */
const boxRoot = new THREE.Group();
scene.add(boxRoot);

let voxMesh = null;    // 单个 InstancedMesh（按实例色着色，一个 draw call）
let voxBoxes = [];     // Y 升序，供点选反查与取景
let grow = null;       // 渐进生长：{ total, start, duration, ys }

function clearBoxes() {
  grow = null;
  if (voxMesh) {
    boxRoot.remove(voxMesh);
    voxMesh.geometry.dispose();
    voxMesh.material.dispose();
    voxMesh = null;
  }
  voxBoxes = [];
}

function addBoxes(boxes) {
  clearBoxes();
  if (!Array.isArray(boxes) || !boxes.length) return 0;

  // Y 升序 → 「低于阈值的高度全显示」即整体自下而上长高
  const sorted = boxes.slice().sort((a, b) => a.y - b.y);

  const geo = new THREE.BoxGeometry(1, 1, 1);
  const mat = new THREE.MeshStandardMaterial({ roughness: 0.82, metalness: 0.0 });
  const mesh = new THREE.InstancedMesh(geo, mat, sorted.length);

  const m = new THREE.Matrix4();
  const p = new THREE.Vector3();
  const q = new THREE.Quaternion();
  const s = new THREE.Vector3();
  const col = new THREE.Color();
  for (let i = 0; i < sorted.length; i++) {
    const b = sorted[i];
    p.set(b.x, b.y, b.z);
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
  voxMesh = mesh;
  voxBoxes = sorted;

  const bb = computeBoxesAABB(sorted);
  if (!bb.isEmpty()) fitCameraToBox(bb);   // 先按全量构图对准相机，避免生长中镜头漂移

  const total = sorted.length;
  const duration = Math.min(7000, Math.max(3000, Math.round(total / 2)));
  grow = { total, start: performance.now(), duration, ys: sorted.map((b) => b.y) };
  setStatus(`生成体素模型 · ${total} 体素`);
  return total;
}

function growTo(threshold) {
  if (!grow || !voxMesh) return;
  const ys = grow.ys;
  let n = 0;
  while (n < ys.length && ys[n] <= threshold) n++;
  if (voxMesh.count !== n) voxMesh.count = n;
}

function finishGrow() {
  if (!grow) return;
  if (voxMesh) voxMesh.count = grow.total;
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
  if (!voxMesh) return;
  pointer.x = (e.clientX / innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObject(voxMesh, false);
  if (hits.length) {
    const b = voxMesh.userData.boxes[hits[0].instanceId];
    if (b) setStatus(`选中：${b.label || b.role || "未知"}`);
  }
});

/* ================= ACP：调 Agent，读事件流 ================= */
function toolLabel(title) {
  if (!title) return "工具";
  if (title.includes("compute_geometry")) return "几何计算";
  if (title.includes("geometry_to_boxes")) return "体素化";
  if (title === "Read") return "读知识库";
  if (title === "Write") return "写中间文件";
  if (title === "Bash") return "跑装配脚本";
  return title.replace(/^mcp__[^_]+__/, "");
}

/* 实例图谱收割：Agent 把 instance.json 打印进流里（Read/Bash），其 rawOutput 带
 * 工具的行号前缀（`1\t{`），剥掉后再定位最外层 {...} 并 JSON.parse。
 * 必须校验 data.courtyards 才认 —— 否则 SKILL.md 里那段骨架示例会被误收。 */
function harvestInstance(raw) {
  if (typeof raw !== "string" || raw.length < 200) return null;
  const text = raw.split("\n").map((l) => l.replace(/^\s*\d+\t/, "")).join("\n");
  const i = text.indexOf("{");
  const j = text.lastIndexOf("}");
  if (i < 0 || j <= i) return null;
  try {
    const o = JSON.parse(text.slice(i, j + 1));
    if (o && o.data && Array.isArray(o.data.courtyards) && o.data.courtyards.length) return o;
  } catch { /* 不是完整的实例图谱 */ }
  return null;
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

    // v3：Agent 不再调 ④⑤，改为把 instance.json 打印进流里 —— 这里收割
    if (upd.rawOutput) {
      const inst = harvestInstance(upd.rawOutput);
      if (inst) state.instance = inst;        // 保留最后一次成功的
    }

    if (!name.includes("compute_geometry") || !upd.rawOutput) return;
    // rawOutput 形如 {"result":"<几何 JSON 字符串>"}（两层）；
    // 若输出过大被 harness 落盘，则是 <persisted-output> 文本，JSON.parse 会失败 → 跳过
    try {
      const outer = JSON.parse(upd.rawOutput);
      if (typeof outer.result !== "string") return;
      const arr = JSON.parse(outer.result);
      if (Array.isArray(arr) && arr.length && arr[0] && arr[0].center) {
        state.geometry = arr;          // 保留最后一次成功的
      }
    } catch { /* 大输出被落盘，忽略 */ }
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
  const state = { text: "", geometry: null, instance: null, tools: 0, failed: 0 };
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

/* ================= MCP：前端直连出体素 ================= */
async function mcpCall(name, args) {
  const resp = await fetch(MCP_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json, text/event-stream",
    },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 1, method: "tools/call",
      params: { name, arguments: args },
    }),
  });
  if (!resp.ok) throw new Error(`MCP 返回 HTTP ${resp.status}`);
  const j = await resp.json();
  if (j.error) throw new Error(j.error.message || "MCP 调用失败");
  const r = j.result || {};
  const text = r.content && r.content[0] && r.content[0].text;
  if (r.isError) throw new Error(text || "工具执行失败");
  if (!text) throw new Error("MCP 返回为空");
  return JSON.parse(text);
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
  statusEl.textContent = msg || "";
  statusEl.classList.toggle("busy", busy);
  statusEl.classList.remove("hidden");
  clearTimeout(statusTimer);
  if (!busy) statusTimer = setTimeout(() => statusEl.classList.add("hidden"), 2600);
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
let busy = false;

function onAgentEvent(ev) {
  if (ev.type === "text") { updateAgentChat(ev.text); return; }
  if (ev.type === "tool") {
    const mark = ev.phase === "failed" ? "✗" : ev.phase === "done" ? "✓" : "…";
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
  setStatus("Agent 正在推导骨架…", true);

  try {
    const state = await runAgent(text, onAgentEvent);
    if (state.text) updateAgentChat(state.text);

    // ④：Agent 把实例图谱打印进流里 → 前端直连 MCP 算几何（v3 起 ④ 归前端）
    let geometry = state.geometry;          // Agent 若仍自己调了 ④，用它的结果
    if (!geometry && state.instance) {
      setStatus("实例图谱就绪 → 几何计算…", true);
      geometry = await mcpCall("compute_geometry", { instance: state.instance });
    }

    if (!geometry) {
      setStatus("Agent 未产出实例图谱，请重试或换个说法");
      appendChat("agent", (state.text ? "\n\n" : "") +
        "（本次未取到实例图谱 —— Agent 可能在装配阶段被中断，换一种描述再试。）");
      return;
    }

    setStatus(`几何就绪 · ${geometry.length} 构件 → 体素化…`, true);
    const boxes = await mcpCall("geometry_to_boxes", { geometry });
    const n = addBoxes(boxes);
    setStatus(`已生成 · ${n} 体素`);
  } catch (e) {
    setStatus(`出错：${e.message}`);
    appendChat("agent", "（出错：" + e.message + "）");
  } finally {
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
