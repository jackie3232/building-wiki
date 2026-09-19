// BUILDING.WIKI · 图谱视图 · 对外接口与交互
// ---------------------------------------------------------------------------
// 展示对象 = 支撑当前模型的**实例图谱本身**（后端随 /api/command 响应回传，main.js 存为
// currentGraph）。纯展示：不另取数据、不落盘、不改几何。
//
// 这是**关系图**，不是方位图：节点摆在哪由力导向按连接关系决定，图上没有指北针、没有
// 临街线 —— 方位是 3D 模型的职责，模型本身就是相对方位的可视化；图谱负责展示的是
// 「实体之间有什么关系」。组织基调：包含为骨（域 ⊃ 院落 ⊃ 建筑/门/附属）、联通为用
// （门连通相邻院落，是空间使用/行走的主连接器；动生于静）。
//
// 交互：拖节点（力会重新摊开）· 悬停高亮邻接 · 滚轮缩放 · 拖背景平移 · 图例点选筛选。
// 屏幕坐标 → 图坐标一律走 getScreenCTM().inverse()，让 SVG 自己处理 viewBox 与缩放，
// 不手算 letterbox 偏移。
// ---------------------------------------------------------------------------
import { RELS, buildModel } from "./model.js";
import { createLayout } from "./layout.js";
import { createRenderer } from "./render.js";

const NS = "http://www.w3.org/2000/svg";

let active = false;
let dictMap = null;
let session = null;

export function isGraphViewActive() { return active; }

async function loadDict() {
  if (dictMap) return dictMap;
  const resp = await fetch("/api/dict");
  if (!resp.ok) throw new Error(`命名字典 HTTP ${resp.status}`);
  const raw = await resp.json();
  const map = {};
  for (const [cat, items] of Object.entries(raw)) {
    if (cat === "meta" || !items || typeof items !== "object") continue;
    for (const [k, v] of Object.entries(items)) {
      if (v && typeof v === "object" && typeof v.label === "string") {
        map[k] = { label: v.label, desc: v.desc || "" };
      }
    }
  }
  dictMap = map;
  return map;
}

export function exitGraphView() {
  if (!active) return false;
  active = false;
  if (session) { session.view.stop(); session.detach(); session = null; }
  document.body.classList.remove("graphing");
  const cv = document.getElementById("graph-canvas");
  if (cv) cv.replaceChildren();
  const lg = document.getElementById("graph-legend");
  if (lg) lg.replaceChildren();
  return true;
}

export async function enterGraphView(graph) {
  if (!graph || !graph.data) return false;
  const cv = document.getElementById("graph-canvas");
  if (!cv) return false;

  exitGraphView();
  document.body.classList.add("graphing");      // 先显示容器，尺寸才量得到真值

  let dict = {};
  try { dict = await loadDict(); } catch (e) { dict = {}; }

  const box = cv.getBoundingClientRect();
  /* 图谱视图是全屏的（工具栏浮在画布上、不占高度），故回落值直接用整窗尺寸 ——
     原先的 innerHeight-140 是为「顶部标题 + 底部输入区」预留的，那两处现已不在画布上方/下方。 */
  const W = Math.max(560, Math.round(box.width || innerWidth));
  const H = Math.max(380, Math.round(box.height || innerHeight));

  const model = buildModel(graph);
  const view = createLayout(model, W, H);

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.setAttribute("role", "img");
  const layers = document.createElementNS(NS, "g");
  svg.appendChild(layers);

  const renderer = createRenderer(layers, view, dict, model.meta);
  cv.replaceChildren(svg);

  /* ---------------- 视口（缩放/平移） ---------------- */
  const zoom = { k: 1, x: 0, y: 0 };
  const applyZoom = () => layers.setAttribute("transform",
    `translate(${zoom.x.toFixed(1)}, ${zoom.y.toFixed(1)}) scale(${zoom.k.toFixed(3)})`);

  const local = (ev) => {                       // 屏幕 → 图坐标（SVG 自己算 viewBox 与缩放）
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    return pt.matrixTransform(layers.getScreenCTM().inverse());
  };

  const onWheel = (e) => {
    e.preventDefault();
    const k = Math.min(4, Math.max(0.5, zoom.k * (e.deltaY < 0 ? 1.13 : 1 / 1.13)));
    zoom.k = k;
    zoom.x = (W / 2) * (1 - k);                 // 以画布中心为锚，缩放时中心不跑
    zoom.y = (H / 2) * (1 - k);
    applyZoom();
  };
  svg.addEventListener("wheel", onWheel, { passive: false });

  let pan = null;
  const onPanDown = (e) => {
    if (e.target.closest && e.target.closest(".gr-node")) return;   // 节点拖拽另走一条链
    pan = { cx: e.clientX, cy: e.clientY, ox: zoom.x, oy: zoom.y };
    svg.setPointerCapture(e.pointerId);
  };
  const onPanMove = (e) => {
    if (!pan) return;
    const r = svg.getBoundingClientRect();
    zoom.x = pan.ox + (e.clientX - pan.cx) * (W / r.width);
    zoom.y = pan.oy + (e.clientY - pan.cy) * (H / r.height);
    applyZoom();
  };
  const onPanUp = () => { pan = null; };
  svg.addEventListener("pointerdown", onPanDown);
  svg.addEventListener("pointermove", onPanMove);
  svg.addEventListener("pointerup", onPanUp);

  /* ---------------- 节点：拖拽 + 悬停高亮 ---------------- */
  const incident = new Map();                   // 节点 id → 与它相连的边
  for (const ee of renderer.edgeEls) {
    for (const id of [ee.link.source.id, ee.link.target.id]) {
      if (!incident.has(id)) incident.set(id, []);
      incident.get(id).push(ee);
    }
  }

  function focus(node) {
    const keep = new Set([node.id]);
    for (const ee of incident.get(node.id) || []) {
      keep.add(ee.link.source.id); keep.add(ee.link.target.id);
      ee.line.classList.add("is-hot");
    }
    for (const ne of renderer.nodeEls) ne.g.classList.toggle("is-hot", keep.has(ne.node.id));
    layers.classList.add("has-focus");
  }
  function blur() {
    layers.classList.remove("has-focus");
    for (const ne of renderer.nodeEls) ne.g.classList.remove("is-hot");
    for (const ee of renderer.edgeEls) ee.line.classList.remove("is-hot");
  }

  for (const ne of renderer.nodeEls) {
    ne.g.addEventListener("pointerenter", () => focus(ne.node));
    ne.g.addEventListener("pointerleave", blur);
    ne.g.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      ne.g.setPointerCapture(e.pointerId);
      ne.g.classList.add("is-drag");
      const p = local(e);
      view.pin(ne.node, p.x, p.y);
      const mv = (ev) => { const q = local(ev); view.pin(ne.node, q.x, q.y); };
      const up = () => {
        ne.g.removeEventListener("pointermove", mv);
        ne.g.removeEventListener("pointerup", up);
        ne.g.classList.remove("is-drag");
        view.unpin(ne.node);
      };
      ne.g.addEventListener("pointermove", mv);
      ne.g.addEventListener("pointerup", up);
    });
  }

  /* ---------------- 图例：点选即筛选同类关系 ---------------- */
  const legend = document.getElementById("graph-legend");
  let picked = null;
  const legendEls = [];
  if (legend) {
    legend.replaceChildren();
    for (const r of RELS) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "gr-legend-item";
      b.dataset.rel = r.rel;
      const rl = dict[r.rel];                    // 关系中文名/释义走命名字典（与节点一致，前端不另存词表）
      b.title = (rl && rl.desc) || r.desc || "";
      const sw = document.createElement("span");
      sw.className = `gr-swatch gr-rel-${r.rel}`;
      const nm = document.createElement("span");
      nm.textContent = (rl && rl.label) || r.label || r.rel;
      b.append(sw, nm);
      b.addEventListener("click", () => {
        picked = picked === r.rel ? null : r.rel;
        for (const ee of renderer.edgeEls) ee.line.classList.toggle("is-sel", ee.link.rel === picked);
        for (const el of legendEls) el.classList.toggle("is-on", el.dataset.rel === picked);
        layers.classList.toggle("has-filter", !!picked);
      });
      legend.appendChild(b);
      legendEls.push(b);
    }
  }

  /* ---------------- 标题 ---------------- */
  const title = document.getElementById("graph-title");
  if (title) {
    const data = graph.data || {};
    title.replaceChildren();
    const a = document.createElement("span");
    a.textContent = `实例图谱 · ${(dict[data.type] && dict[data.type].label) || data.type || "instance"}`;
    const b = document.createElement("span");
    b.className = "sub";
    const bits = [`${data.jin ?? "?"} 进`, `${model.nodes.length} 节点`,
                  `${model.links.length} 条关系`, "力导向"];
    if (model.meta.zeroCoord) bits.push("零坐标");
    b.textContent = bits.join(" · ");
    title.append(a, b);
  }

  /* ---------------- 起跑 ---------------- */
  view.simulation.on("tick", renderer.update);
  view.start();

  session = {
    view,
    detach() {
      svg.removeEventListener("wheel", onWheel);
      svg.removeEventListener("pointerdown", onPanDown);
      svg.removeEventListener("pointermove", onPanMove);
      svg.removeEventListener("pointerup", onPanUp);
    },
  };
  active = true;
  return true;
}

const exitBtn = document.getElementById("btn-exit-graph");
if (exitBtn) exitBtn.addEventListener("click", () => exitGraphView());
