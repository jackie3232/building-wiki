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
// 门（gate）节点只画真门（垂花门 / 宅门）—— 穿堂不是门，它是正房明间的贯通做法，
// 挂在正房（building）节点上显示，不在这儿。
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
  zucheng: "包含",            // 静：域 ⊃ 院落 ⊃ 建筑/门/附属
  liantong: "联通",           // 动：经门 / 明间门洞 / 穿堂，由一空间通达另一空间
};
const TYPE_LABEL = { siheyuan: "四合院" };   // 图谱类型中文名（字典补「建筑类型」类目后应改从字典取）
const SIDE_CN = { south: "南", north: "北", east: "东", west: "西" };
/* 联通弧线的侧偏量：够两条边分开，又不至于甩到别的节点身上 */
const ARC_OFF = 18;

function subtitleOf(n) {
  if (n.cat === "domain") return n.jin != null ? `${n.jin} 进` : "";
  if (n.cat === "court") return n.court && n.court.sequence != null ? `第 ${n.court.sequence} 进` : "";
  if (n.cat === "building") return n.court ? (n.court.name || `第${n.court.sequence}进`) : "";
  if (n.cat === "gate") return n.doorNote || (n.shared ? "分界门" : (n.exit ? "后门" : (n.entrance ? "正门" : "门")));
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
  out.push(`${lbl(n.role)}  (${n.role || "?"})`);
  const d = dsc(n.role);
  if (d) out.push(d);

  if (n.cat === "court") {
    out.push(`第 ${n.court.sequence} 进院落${n.court.name ? " · " + n.court.name : ""}`);
    const b = n.boundary || {};
    const parts = Object.entries(b).map(([s, k]) => `${SIDE_CN[s] || s}侧：${lbl(k)}`);
    if (parts.length) out.push("无建筑的界：" + parts.join("、"));
    if (n.entry && n.entry.thru) {
      out.push(`南界入口：经上一进「${lbl(n.entry.thru.of)}」明间过厅进入`);
      out.push("过厅 = 正房明间：南门(内院进) → 北门(穿堂出口·达本院) —— 两道门");
      out.push("穿堂属上一进那座正房 · 不立为门节点");
    }
  }
  if (n.cat === "building") {
    if (n.encloses) out.push(n.encloses);
    if (n.mirror) out.push(`与「${lbl(n.mirror)}」东西对称`);
    const info = n.info || {};
    const bits = [];
    if (info.miankuo != null) bits.push(`面阔 ${info.miankuo} 间`);
    if (info.jinshen != null) bits.push(`进深 ${info.jinshen} 间`);
    if (bits.length) out.push(bits.join(" · "));
    // 穿堂：明间前后贯通，连通下一进院。它是这座房子的做法 → 随房子归属本院，不是门。
    if (info.chuantang) {
      const doors = (n.doors || []).map((d) => `${d.side}（${d.note}）`).join(" → ");
      out.push(`正房南北两端各一门（内院↔后罩院的载体）：${doors}`);
      out.push("明间南北贯通作过厅 · 门洞不立节点，记在边上");
    } else if (n.thru) out.push(`明间前后贯通作穿堂 · 通「${n.thru.to}」`);
  }
  if (n.cat === "gate") {
    if (n.doorNote) out.push(`${n.label || "门"} · ${n.doorNote}${n.note ? " · " + n.note : ""}`);
    if (n.shared && n.between) {
      out.push(`分界：${n.between.map((x) => `「${x}」`).join(" | ")}`);
      out.push("相邻两院的共享边界 · 不独属于任一院，故归于域");
    }
    if (n.embeddedIn && n.embeddedIn !== n.role) out.push(`嵌于「${lbl(n.embeddedIn)}」`);
    if (n.entrance) out.push("宅院正门 · 街 → 院（坎宅巽门）");
    if (n.exit) out.push("宅院后门 · 院 → 北胡同（西北角一间改门道，宅后临街才设）");
  }
  if (n.cat === "aux") out.push("附属构件，挂在庭院上");
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
    // 联通画成**弧线**：它与包含常常连的是同一对节点（院—建筑），两条直线会叠成一条，
    // 静/动两层就看不出来了。给动线一个固定侧偏，两条边分列两侧。
    const line = el(l.rel === "liantong" ? "path" : "line",
                    { class: `gr-edge gr-rel-${l.rel}` }, gEdges);
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

    // 两侧翼是同名的两个不同实体（东厢房 / 西厢房），标签带侧位才分得清谁是谁。
    const sidePrefix = (n.side === "east" || n.side === "west") ? (SIDE_CN[n.side] || "") : "";
    const onDot = n.cat === "domain" ? " on-dot" : "";
    const main = el("text", { class: `gr-label${onDot}` }, gLabels);
    main.textContent = n.cat === "domain" ? (TYPE_LABEL[n.role] || n.role)
      : n.cat === "court" ? (n.name || (n.court && n.court.id) || "庭院")
        : (n.label || sidePrefix + lbl(n.role));

    const subText = subtitleOf(n);
    const sub = subText ? el("text", { class: `gr-sub${onDot}` }, gLabels) : null;
    if (sub) sub.textContent = subText;
    return { g, main, sub, node: n, r: radiusOf(n) };
  });

  function update() {
    for (const e of edgeEls) {
      const a = e.link.source, b = e.link.target;
      const [x1, y1, x2, y2] = seg(a, b, radiusOf(a), radiusOf(b));
      if (e.link.rel === "liantong") {
        const dx = x2 - x1, dy = y2 - y1;
        const len = Math.hypot(dx, dy) || 1;
        const nx = -dy / len, ny = dx / len;             // 弦的法向
        const cx0 = (x1 + x2) / 2, cy0 = (y1 + y2) / 2;
        // 朝哪侧弯：挑**离不相干节点更远**的一侧——固定侧偏在小画布上会把动线甩到
        // 旁边建筑的圆上（四进 1024x640 实测：后门⇢后罩院 压住厢房）。
        // 迟滞 6px：两侧差不多时不来回翻，弧线才不会抖。
        let side = 1, best = -Infinity;
        for (const s of [1, -1]) {
          const px = cx0 + nx * ARC_OFF * s, py = cy0 + ny * ARC_OFF * s;
          let clear = Infinity;
          for (const ne of nodeEls) {
            if (ne.node === a || ne.node === b) continue;
            clear = Math.min(clear, Math.hypot(px - ne.node.x, py - ne.node.y) - ne.r);
          }
          const score = clear + (s === e.lastSide ? 6 : 0);
          if (score > best) { best = score; side = s; }
        }
        e.lastSide = side;
        const mx = cx0 + nx * ARC_OFF * side;
        const my = cy0 + ny * ARC_OFF * side;
        e.line.setAttribute("d",
          `M${x1.toFixed(1)},${y1.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`);
        continue;
      }
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
