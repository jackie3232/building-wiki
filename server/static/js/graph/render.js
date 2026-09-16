// BUILDING.WIKI · 图谱视图 · 渲染（SVG）
// ---------------------------------------------------------------------------
// 三层 DOM，只建一次，之后每帧只改属性 —— 不重建节点，画面才不会闪：
//   gEdges  边（线，按关系类型上色/上虚线）
//   gNodes  节点（圆点）
//   gLabels 标签（独立一层、绝对坐标：若挂进已 translate 的节点组里，坐标系就会叠加）
//
// 标签一律排在圆点正下方居中。力导向下节点会缓慢游动，标签若按「半径方向甩出去」就会
// 随方向左右横跳；正下方是唯一在持续运动下仍然稳定的排法。
//
// 中文名一律取自后端命名字典（role -> label），前端不另存词表；字典缺 key 就回落显示 key。
// 例外是驱动链的三个节点（模数 / 几何引擎 / 体素模型）—— 它们是视图为表达「图谱如何驱动
// 模型」而引入的**算子节点**，不是图谱实体，故其名称属视图词汇，不取自图谱字典。
// ---------------------------------------------------------------------------

const NS = "http://www.w3.org/2000/svg";

function el(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  if (attrs) for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

export function makeDictReader(dict) {
  const lbl = (k) => (k ? ((dict[k] && dict[k].label) || k) : "—");
  const dsc = (k) => (k && dict[k] ? dict[k].desc || "" : "");
  return { lbl, dsc };
}

const REL_LABEL = {
  zucheng: "组成", xulie: "序列", weihe: "围合",
  qianzhi: "嵌于", duichen: "对称", fushu: "附属", qudong: "驱动",
};
const OP_LABEL = { norms: "模数", engine: "几何引擎", model: "体素模型" };
const TYPE_LABEL = { siheyuan: "四合院" };   // 图谱类型中文名（字典补「建筑类型」类目后应改从字典取）
const SIDE_CN = { south: "南", north: "北", east: "东", west: "西" };

function subtitleOf(n) {
  if (n.cat === "domain") return n.jin != null ? `${n.jin} 进` : "";
  if (n.cat === "court") return n.court && n.court.sequence != null ? `第 ${n.court.sequence} 进` : "";
  // 两侧翼：多进院落里会同时存在两对厢房，主标签都是「东厢房 / 西厢房」，
  // 必须补一行「属于哪个院」才分得清 —— 主标签保持短，归属交给副标题。
  if (n.refs === "flank" && n.court) return n.court.name || n.court.id;
  if (n.cat === "norms") return n.modus != null ? `${n.modus} m / 间` : "";
  if (n.cat === "engine") return "④";
  if (n.cat === "model") return "⑤";
  return "";
}

function nodeTip(n, dict, meta) {
  const { lbl, dsc } = makeDictReader(dict);
  const out = [];
  if (n.cat === "domain") {
    out.push(`域 · ${TYPE_LABEL[n.role] || n.role}`);
    if (n.jin != null) out.push(`${n.jin} 进院落`);
    if (meta.zeroCoord) out.push("零坐标 · 只含语义，不含几何");
    return out.join("\n");
  }
  if (OP_LABEL[n.cat]) {
    out.push(`${OP_LABEL[n.cat]}（驱动链节点，非图谱实体）`);
    if (n.cat === "norms") out.push("appliedRules.norms —— 换算标准，由它定出各构件的真实尺寸");
    if (n.cat === "engine") out.push("④ 几何计算引擎 —— 据拓扑与模数算出绝对坐标");
    if (n.cat === "model") out.push("⑤ 几何造型引擎 —— 输出体素 BOX");
    return out.join("\n");
  }
  out.push(`${lbl(n.role)}  (${n.role || "?"})`);
  const d = dsc(n.role);
  if (d) out.push(d);
  if (n.cat === "court" && n.court) out.push(`庭院 ${n.court.id}${n.court.name ? " · " + n.court.name : ""}`);
  const info = n.info || {};
  const bits = [];
  if (n.side) bits.push(`位于${SIDE_CN[n.side] || n.side}侧`);
  if (info.provider) bits.push(`由「${lbl(info.provider)}」的后檐墙充当这侧的界`);
  else if (info.kind) bits.push(`墙型：${lbl(info.kind)}`);
  if (info.miankuo != null) bits.push(`面阔 ${info.miankuo} 间`);
  if (info.jinshen != null) bits.push(`进深 ${info.jinshen} 间`);
  if (info.chuantang) bits.push("明间穿堂");
  if (bits.length) out.push(bits.join(" · "));
  return out.join("\n");
}

/* 把线段裁到两端圆的外缘：线从圆边出发，不钻进圆里 */
function seg(a, b, ra, rb) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;
  return [a.x + ux * ra, a.y + uy * ra, b.x - ux * rb, b.y - uy * rb];
}

export function createRenderer(layers, view, dict, meta) {
  const { nodes, links, radiusOf } = view;
  const { lbl } = makeDictReader(dict);

  const gEdges = el("g", null, layers);
  const gNodes = el("g", null, layers);
  const gLabels = el("g", null, layers);

  const edgeEls = links.map((l) => {
    const line = el("line", { class: `gr-edge gr-rel-${l.rel}` }, gEdges);
    const rel = REL_LABEL[l.rel] || l.rel;
    const t = el("title", null, line);
    t.textContent = [`${lbl(l.source.role)} —${rel}→ ${lbl(l.target.role)}`, l.note]
      .filter(Boolean).join("\n");
    return { line, link: l };
  });

  const nodeEls = nodes.map((n) => {
    const g = el("g", { class: `gr-node gr-cat-${n.cat}` }, gNodes);
    el("circle", { class: "gr-dot", r: radiusOf(n).toFixed(1) }, g);
    const tip = nodeTip(n, dict, meta);
    if (tip) { const t = el("title", null, g); t.textContent = tip; }

    // 两侧翼是同名的两个不同实体（东厢房 / 西厢房），标签必须带侧位 ——
    // 否则图上会出现两个都叫「厢房」的点，读者无从分辨谁是谁。
    const sidePrefix = n.refs === "flank" && n.side ? (SIDE_CN[n.side] || "") : "";
    const onDot = n.cat === "domain" ? " on-dot" : "";
    const main = el("text", { class: `gr-label${onDot}` }, gLabels);
    main.textContent = OP_LABEL[n.cat]
      || (n.cat === "domain" ? (TYPE_LABEL[n.role] || n.role)
        : n.cat === "court" ? (n.name || (n.court && n.court.id) || "庭院")
          : sidePrefix + lbl(n.role));

    const subText = subtitleOf(n);
    const sub = subText ? el("text", { class: `gr-sub${onDot}` }, gLabels) : null;
    if (sub) sub.textContent = subText;
    return { g, main, sub, node: n, r: radiusOf(n) };
  });

  function update() {
    for (const e of edgeEls) {
      const a = e.link.source, b = e.link.target;
      const [x1, y1, x2, y2] = seg(a, b, radiusOf(a), radiusOf(b));
      e.line.setAttribute("x1", x1.toFixed(1));
      e.line.setAttribute("y1", y1.toFixed(1));
      e.line.setAttribute("x2", x2.toFixed(1));
      e.line.setAttribute("y2", y2.toFixed(1));
    }
    for (const n of nodeEls) {
      const x = n.node.x, y = n.node.y;
      n.g.setAttribute("transform", `translate(${x.toFixed(1)}, ${y.toFixed(1)})`);
      const center = n.node.cat === "domain";       // 域是中心节点，文字压在圆内更聚气
      n.main.setAttribute("x", x.toFixed(1));
      n.main.setAttribute("y", (y + (center ? 1 : n.r + 13)).toFixed(1));
      if (n.sub) {
        n.sub.setAttribute("x", x.toFixed(1));
        n.sub.setAttribute("y", (y + (center ? 16 : n.r + 27)).toFixed(1));
      }
    }
  }
  update();

  return { update, nodeEls, edgeEls, groups: { gEdges, gNodes, gLabels } };
}
