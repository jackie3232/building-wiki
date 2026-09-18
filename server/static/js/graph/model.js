// BUILDING.WIKI · 图谱视图 · 数据模型（实例图谱 → 关系图）
// ---------------------------------------------------------------------------
// 输入 = 一张实例图谱（零坐标）；输出 = { nodes, links }，**只含关系，不含坐标**。
// 坐标由 layout.js 的力导向算。
//
// 组织基调：**静为骨、动为用**，两类关系分层叠加。
//   · 包含（zucheng）= 静：域 ⊃ 院落 ⊃ 建筑/附属；跨院之物 ⊃ 门。回答"这是什么院子"。
//   · 联通（liantong）= 动：经门 / 明间门洞 / 穿堂，由一空间通达另一空间。回答"怎么走"。
//   · 只有**独立门屋**（宅门 / 垂花门 / 后门）才立门节点，并走「院—门—院」两段；
//     建筑上的门洞（明间门、穿堂）**不立节点**，直接连「院—建筑」，边上记经什么过
//     —— 与「穿堂不立门节点」同一条律：能归属到一座建筑的通道，就随那座建筑走。
//   · 围合/对称/嵌于 全部降级为节点属性；附属归入包含。
//     旧版 7 种连线同层平铺，正是"乱"的根源——此处先收敛为 2 类（静 1 + 动 1）。
//
// 归属原则：**能归属到某一进院的，归该院；归属不到任何一进院的，归域（根）**。
//   · 垂花门：独立门屋，建于院际卡子墙正中，两侧院都不独享 → 无归属 → 归域。
//   · 穿堂：**不是门**。它是上一进北房「明间前后贯通」的做法，属那座正房 → 属上一进院。
//     有明确归属，故**不立门节点**，只挂在建筑节点上（thru：通向下一进院）。
//     图谱侧对应 ring.south.thru（而非 ring.south.gate）——gate 只记真正的门。
//   · 宅门：嵌于首院南界倒座房、不跨院 → 归首院。
//
// 墙（外围围墙/卡子墙）不立节点：某侧无建筑只是"那侧是围墙"，写成院落节点的边界属性。
// 图谱没声明的实体一律不画（忠实投影，不替图谱补想象）。
// ---------------------------------------------------------------------------

/* 两类关系：zucheng = 包含（静·骨架），liantong = 联通（动·动线）。 */
export const RELS = [
  { rel: "zucheng", label: "包含", desc: "静态组织：域 ⊃ 院落 ⊃ 建筑/门/附属" },
  { rel: "liantong", label: "联通", desc: "动态组织（动线）：经门 / 明间门洞 / 穿堂，由一空间通达另一空间" },
];
const REL_SET = new Set(RELS.map((r) => r.rel));

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
    // 朝院门洞：各房门窗均向院内开辟，门在明间。图谱只记**位置**，不记开向——
    // 开向由房屋所在侧推得（北房朝南、南房朝北、东厢朝西、西厢朝东），属几何事实。
    door: e.door ?? null,
  };
  const r = (court.ring || {})[side];
  if (r) {
    // thru = 「经何物进入本院」（如经上一进正房明间穿堂），与 gate（真门）互斥。
    return { ...base, provider: r.provider ?? null, kind: r.kind ?? null,
             gate: r.gate ?? null, thru: r.thru ?? null };
  }
  const enc = court.enclosure || {};
  let gate = null;
  if (side === "north" && enc.northGate) gate = roleOf(enc.northGate);
  else if (side === "south" && enc.southGate) gate = roleOf(enc.southGate);
  else if (side === "south" && isSouthmost && e.gate) gate = roleOf(e.gate) || "zhaimen";
  return { ...base, provider: base.role, kind: base.role ? "houyanqiang" : "weiqiang",
           gate, thru: null };
}

const cid = (c) => String(c.id || `cy${c.sequence}`);

export function buildModel(graph) {
  const data = (graph && graph.data) || {};
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

  /* —— 院落：按中轴序列；域 ⊃ 院落（包含）—— */
  const courtNodes = courts.map((c) => {
    const rs = (c.ring || {}).south || {};
    const n = push({
      id: cid(c), cat: "court", role: roleOf(c.center) || "tingyuan",
      name: c.name || "", court: c, boundary: {},
      // 南界入口：gate = 真门（宅门/垂花门）；thru = 经上一进正房明间穿堂（不是门，不立节点）
      entry: rs.gate ? { gate: rs.gate } : (rs.thru ? { thru: rs.thru } : null),
    });
    link(root, n, "zucheng");
    return n;
  });

  /* —— 每院自身围合界（北/东/西；首院另含南=倒座房）——
     · 有建筑 → 建筑节点，包含于本院（"围合"是其功能，记进属性，不另立"围合"边）。
     · 无建筑 → 该侧边界属性（墙），不立节点。 */
  const bnode = new Map();          // `${院id}:${side}` -> 建筑节点（动线要按侧找它）
  courts.forEach((c, i) => {
    const cn = courtNodes[i];
    const sides = ["north", "east", "west"];
    if (i === 0) sides.push("south");   // 首院南界 = 倒座房（宅门嵌其上）
    for (const side of sides) {
      const info = sideInfo(c, side, i === 0 && side === "south");
      if (info.provider) {
        const bn = push({
          id: `B:${cid(c)}:${side}`, cat: "building", role: info.provider,
          side, info, court: c,
          encloses: `${SIDE_TAG[side]}面 · 围合第${c.sequence}进院`,
        });
        bnode.set(`${cid(c)}:${side}`, bn);
        link(cn, bn, "zucheng");
        // 穿堂正房 = 内院↔后罩院之间的载体，**两端各拎出一个门节点**：
        //   内院 —南门(明间)→ 正房 —北门(穿堂)→ 后罩院
        // 南门朝内院、北门朝后罩院；两门都是这座正房的开门，故 zucheng 于正房，
        // 同时串进 liantong 动线，让「进院—穿正房—达后院」是一条显式的门链。
        if (side === "north" && info.chuantang && courts[i + 1]) {
          const fromName = c.name || `第${c.sequence}进`;
          const toName = courts[i + 1].name || `第${courts[i + 1].sequence}进`;
          bn.doors = [
            { side: "南门(明间)", note: `「${fromName}」进正房` },
            { side: "北门(穿堂)", note: `出正房达「${toName}」` },
          ];
          const sdoor = push({
            id: `G:${cid(c)}:zdS`, cat: "gate", role: "men", label: "正房南门",
            court: c, side: "south", embeddedIn: bn.role, owner: bn.id,
            doorNote: `明间 · 朝${fromName}`, note: `从「${fromName}」进正房`,
          });
          const ndoor = push({
            id: `G:${cid(c)}:zdN`, cat: "gate", role: "men", label: "正房北门",
            court: c, side: "north", embeddedIn: bn.role, owner: bn.id,
            doorNote: `明间 · 朝${toName}`, note: `出正房达「${toName}」`,
          });
          link(bn, sdoor, "zucheng", "正房南门");
          link(bn, ndoor, "zucheng", "正房北门");
          link(cn, sdoor, "liantong", `经正房·南门(明间)`);
          link(sdoor, bn, "liantong", "南门进正房");
          link(bn, ndoor, "liantong", "出正房经北门");
          link(ndoor, courtNodes[i + 1], "liantong", `经正房·北门(穿堂)达「${toName}」`);
        }
      } else if (info.kind) {
        cn.boundary[side] = info.kind;   // 如 weiqiang：该侧是外围围墙，仅作边界属性
      }
    }
  });

  /* —— 对称：同院东西同名建筑 → 节点属性（不另立边） —— */
  courts.forEach((c) => {
    const e = nodes.find((n) => n.id === `B:${cid(c)}:east`);
    const w = nodes.find((n) => n.id === `B:${cid(c)}:west`);
    if (e && w && e.cat === "building" && e.role === w.role) {
      e.mirror = w.role; w.mirror = e.role;
    }
  });

  /* —— 门 ——
     只立「真门」节点：ring.south.gate 有值才画（宅门 / 垂花门）。
     穿堂**不再出现在这里** —— 图谱把它记在 ring.south.thru，属上一进正房，
     已挂在那个建筑节点上（见上）。此处的 s.gate 恒不含 chuantang。
     · 宅门：嵌于首院南界（倒座房东侧），对外、不跨院 → 归属首院。
     · 垂花门：独立门屋，建于院际卡子墙正中，两侧院都不独享 → 归域根，记明「分界哪两院」。 */
  if (courts.length) {
    const c0 = courts[0];
    const s0 = sideInfo(c0, "south", true);
    if (s0.gate) {
      const gn = push({
        id: `G:${cid(c0)}:south`, cat: "gate", role: s0.gate,
        info: s0, embeddedIn: s0.provider, court: c0, entrance: true,
        side: "south", hostId: `B:${cid(c0)}:south`,   // 所嵌的那座房子（布局初值用）
      });
      link(courtNodes[0], gn, "zucheng");   // 宅门属于首院
    }
  }
  for (let i = 1; i < courts.length; i++) {
    const cur = courts[i];
    const prev = courts[i - 1];
    const s = sideInfo(cur, "south", false);
    if (!s.gate) continue;
    const pn = prev.name || `第${prev.sequence}进`;
    const cn2 = cur.name || `第${cur.sequence}进`;
    const gn = push({
      id: `G:${cid(cur)}:south`, cat: "gate", role: s.gate,
      info: s, embeddedIn: s.provider, court: cur,
      shared: true, between: [pn, cn2],
    });
    link(root, gn, "zucheng");   // 共享边界 → 归域
  }

  /* —— 附属构件（影壁）：包含于本院（轻量节点） ——
     游廊当前不在 peripheral 中 → 不生成节点；留待加细节阶段讨论形制与归属后再出现。 */
  courts.forEach((c, i) => {
    (c.peripheral || []).forEach((p, j) => {
      const n = push({ id: `${cid(c)}.aux${j}`, cat: "aux", role: roleOf(p), court: c });
      link(courtNodes[i], n, "zucheng");
    });
  });

  /* —— 后门：嵌于末进（后罩院）北界后罩房的西北角，宅院通往北胡同的出口 ——
     与宅门同法：不是独立门屋，而是「把西北角那间改成门道」，嵌在谁身上就归谁所在的院
     （宅门嵌倒座房 → 归首院；后门嵌后罩房 → 归后罩院）。条件性构件：图谱声明了才画。 */
  let houmen = null;
  if (courts.length) {
    const cLast = courts[courts.length - 1];
    const nLast = sideInfo(cLast, "north", false);
    if (nLast.gate === "houmen") {
      houmen = push({
        id: `G:${cid(cLast)}:north`, cat: "gate", role: nLast.gate,
        info: nLast, embeddedIn: nLast.provider, court: cLast,
        exit: true, at: "northwest", side: "north",
        hostId: `B:${cid(cLast)}:north`,   // 所嵌的那座后罩房（布局初值用）
      });
      link(courtNodes[courts.length - 1], houmen, "zucheng");   // 后门属于末进院
    }
  }

  /* —— 联通（动线）：静是骨架、动是用途，两层叠加在同一张图上 ——
     主轴：街 —宅门→ 外院 —垂花门→ 内院 —正房(南门进·北门出)→ 后罩院 —后门→ 北胡同。
     院内：院 ↔ 每座围合建筑（明间门洞）。穿堂正房就是内院↔后罩院之间的载体。 */
  if (courts.length) {
    courts.forEach((c, i) => {
      const cn = courtNodes[i];
      // 院 ↔ 围合建筑：经该房朝本院的门洞（门洞不立节点，记在边上）
      for (const side of ["north", "south", "east", "west"]) {
        const bn = bnode.get(`${cid(c)}:${side}`);
        if (!bn || !(bn.info && bn.info.door)) continue;
        if (bn.info.chuantang) continue;   // 穿堂正房已在上方按「南门/北门」两端连线，此处不再重复
        link(cn, bn, "liantong", `经${bn.role}明间门洞`);
      }
      // 注：穿堂正房两端（南门→内院 / 北门→后罩院）已在上方建筑循环表达，这里不再重复。
    });
    // 门：只有独立门屋才走「院—门—院」两段；另一端是院外（街/胡同）时不立节点，
    //     只连院内这一段，院外那一头写在边的 note 里。
    for (let i = 1; i < courts.length; i++) {
      const gn = nodes.find((n) => n.id === `G:${cid(courts[i])}:south`);
      if (!gn) continue;
      const note = `经垂花门：${courts[i - 1].name || ""} ↔ ${courts[i].name || ""}`;
      link(courtNodes[i - 1], gn, "liantong", note);
      link(gn, courtNodes[i], "liantong", note);
    }
    const zm = nodes.find((n) => n.id === `G:${cid(courts[0])}:south`);
    if (zm && courtNodes[0]) link(zm, courtNodes[0], "liantong", "街 ↔ 院（正门·坎宅巽门）");
    if (houmen) link(houmen, courtNodes[courtNodes.length - 1], "liantong", "院 ↔ 北胡同（后门·西北角）");
  }

  return { nodes, links, rels: RELS, meta: (graph && graph.meta) || {} };
}
