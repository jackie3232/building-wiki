// BUILDING.WIKI · 图谱视图 · 数据模型（实例图谱 → 关系图）
// ---------------------------------------------------------------------------
// 输入 = 一张实例图谱（零坐标）；输出 = { nodes, links }，**只含关系，不含坐标**。
// 坐标由 layout.js 的力导向算 —— 节点摆在哪由「它连了谁」决定，不按方位摆。
//
// 三条不可漂移的语义约定：
//  ① 方位词（south/north/east/west）是「界」的槽位名，不是画布方位。
//     它只作为边的说明出现（「北面围合」），不参与摆放。
//  ② 与 3D 模型的分工：模型展示**相对方位**，图谱展示**关系与驱动链**。
//     所以这里没有指北针、没有临街线、没有南北弧序。
//  ③ 图谱没声明的实体一律不画（实例未声明 zhaimen 就不出现大门节点）——
//     图谱视图是图谱的忠实投影，不替图谱补想象。
//
// ring：由图谱层 build_instance 显式声明（每侧的界由谁承担 / 是哪类墙 / 开什么门），
// 属零坐标的语义声明，可直接消费。手写或旧版图谱没有 ring 时按 enclosure 就近兜底。
// ---------------------------------------------------------------------------

/* 边 = 关系。rel 是稳定标识，中文名与配色由视图层给。 */
export const RELS = [
  { rel: "zucheng", label: "组成", desc: "域由若干进院落组成" },
  { rel: "xulie", label: "序列", desc: "院落沿中轴按进次排列" },
  { rel: "weihe", label: "围合", desc: "界的承担者围合出庭院" },
  { rel: "qianzhi", label: "嵌于", desc: "门开在某一道界上" },
  { rel: "duichen", label: "对称", desc: "同院东西两侧的同名建筑互为镜像" },
  { rel: "fushu", label: "附属", desc: "游廊、影壁等附属构件挂在庭院上" },
  { rel: "qudong", label: "驱动", desc: "图谱信息驱动出模型的链路" },
];
const REL_SET = new Set(RELS.map((r) => r.rel));

const SIDES = ["south", "north", "east", "west"];
export const SIDE_TAG = { south: "南", north: "北", east: "东", west: "西" };

const roleOf = (o) => (o && o.role) || null;

/* 一侧的界：优先用图谱层声明的 ring；无 ring（手写/旧版图谱）时按 enclosure 兜底。 */
function sideInfo(court, side, isSouthmost) {
  const e = (court.enclosure || {})[side] || {};
  const base = {
    role: roleOf(e),
    miankuo: e.miankuo ?? null,
    jinshen: e.jinshen ?? null,
    chuantang: !!e.chuantang,
  };

  const r = (court.ring || {})[side];
  if (r) {
    return { ...base, provider: r.provider ?? null, kind: r.kind ?? null, gate: r.gate ?? null };
  }

  // 兜底：语义等价于 build_instance 的推导（有建筑 → 其后檐墙充当边界；否则是围墙）
  const enc = court.enclosure || {};
  let gate = null;
  if (side === "north" && enc.northGate) gate = roleOf(enc.northGate);
  else if (side === "south" && enc.southGate) gate = roleOf(enc.southGate);
  else if (side === "south" && isSouthmost && e.gate) gate = roleOf(e.gate) || "zhaimen";
  return {
    ...base,
    provider: base.role,
    kind: base.role ? "houyanqiang" : "weiqiang",
    gate,
  };
}

/* 相邻两院各自描述同一条界 → 合并成一条，否则正房、卡子墙会各画两遍。
   provider 取非空；kind 取更具体的那侧（优先非 weiqiang）；门取并集。 */
function mergeInfo(a, b) {
  if (!a) return b || null;
  if (!b) return a;
  const kinds = [a.kind, b.kind].filter(Boolean);
  return {
    role: a.role || b.role || null,
    provider: a.provider || b.provider || null,
    kind: kinds.find((k) => k !== "weiqiang") || kinds[0] || null,
    gate: a.gate || b.gate || null,
    miankuo: a.miankuo ?? b.miankuo ?? null,
    jinshen: a.jinshen ?? b.jinshen ?? null,
    chuantang: !!(a.chuantang || b.chuantang),
  };
}

export function buildModel(graph) {
  const data = (graph && graph.data) || {};
  const rules = (graph && graph.appliedRules) || {};
  const courts = [...(data.courtyards || [])]
    .sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));

  const nodes = [];
  const links = [];
  const push = (n) => { nodes.push(n); return n; };
  const link = (s, t, rel, note) => {
    if (!s || !t || s === t) return;
    if (!REL_SET.has(rel)) throw new Error(`未知关系类型：${rel}`);
    links.push({ source: s.id, target: t.id, rel, note: note || "" });
  };

  /* —— 域 —— */
  const root = push({ id: "domain", cat: "domain", role: data.type || "instance", jin: data.jin });

  /* —— 庭院 + 序列 —— */
  const courtNodes = courts.map((c) => push({
    id: String(c.id || `cy${c.sequence}`),
    cat: "court",
    role: roleOf(c.center) || "tingyuan",
    name: c.name || "",
    court: c,
  }));
  courtNodes.forEach((n) => link(root, n, "zucheng"));
  for (let i = 1; i < courtNodes.length; i++) link(courtNodes[i - 1], courtNodes[i], "xulie");

  /* —— 横向的界：最南一道 + 每两院之间合并成一道 + 最北一道（共 N+1 道） —— */
  const bounds = [];
  courts.forEach((c, i) => {
    if (i === 0) bounds.push({ side: "south", info: sideInfo(c, "south", true), shared: [i] });
    const next = courts[i + 1];
    bounds.push({
      side: "north",
      info: mergeInfo(sideInfo(c, "north", false), next ? sideInfo(next, "south", false) : null),
      shared: next ? [i, i + 1] : [i],
    });
  });
  bounds.forEach((b, k) => {
    const info = b.info || {};
    if (!info.provider && !info.kind && !info.gate) return;
    const bn = push({
      id: `B${k}`,
      cat: info.provider ? "building" : "wall",
      role: info.provider || info.kind,
      side: b.side,
      info,
      refs: "boundary",
    });
    b.shared.forEach((ci) => link(bn, courtNodes[ci], "weihe", `${SIDE_TAG[b.side]}面围合`));
    if (info.gate) {
      const gn = push({ id: `G${k}`, cat: "gate", role: info.gate, side: b.side, info });
      link(gn, bn, "qianzhi", `开在${SIDE_TAG[b.side]}面界上`);
    }
  });

  /* —— 纵向的界（两侧翼）：同院东西同名建筑互为镜像 —— */
  courts.forEach((c, i) => {
    const flank = {};
    for (const side of ["east", "west"]) {
      const info = sideInfo(c, side, false);
      if (!info.provider && !info.kind) continue;
      const n = push({
        id: `${courtNodes[i].id}.${side}`,
        cat: info.provider ? "building" : "wall",
        role: info.provider || info.kind,
        side,
        info,
        court: c,
        refs: "flank",
      });
      link(n, courtNodes[i], "weihe", `${SIDE_TAG[side]}侧围合`);
      flank[side] = n;
    }
    const [e, w] = [flank.east, flank.west];
    if (e && w && e.cat === "building" && e.role === w.role) link(e, w, "duichen");
  });

  /* —— 附属构件 —— */
  courts.forEach((c, i) => {
    (c.peripheral || []).forEach((p, j) => {
      const n = push({
        id: `${courtNodes[i].id}.aux${j}`,
        cat: "aux",
        role: roleOf(p),
        court: c,
      });
      link(n, courtNodes[i], "fushu");
    });
  });

  /* —— 驱动链：图谱信息如何驱动出模型 —— */
  const norms = rules.norms;
  if (norms) {
    const nn = push({ id: "norms", cat: "norms", role: "modus", modus: norms.modus });
    const en = push({ id: "engine", cat: "engine", role: "geometry" });
    const mn = push({ id: "model", cat: "model", role: "voxel" });
    link(root, nn, "qudong", "应用规则库");
    link(nn, en, "qudong", norms.modus != null ? `模数 ${norms.modus}m` : "");
    link(en, mn, "qudong", "构件 → 体素");
  }

  return { nodes, links, rels: RELS, meta: (graph && graph.meta) || {} };
}
