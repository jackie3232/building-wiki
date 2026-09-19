// BUILDING.WIKI · 图谱视图 · 数据模型（实例图谱 → 关系图）
// ---------------------------------------------------------------------------
// 输入 = 一张实例图谱（零坐标）；输出 = { nodes, links }，**只含关系，不含坐标**。
// 坐标由 layout.js 算（力导向：节点摆在哪由「它连了谁」决定，图上不声称方位）。
//
// 组织基调：**静为骨、动为用**，两类关系分层叠加。
//   · 包含（zucheng）= 静：域 ⊃ 院落 ⊃ 建筑/门/附属。回答"这是什么院子"。
//   · 联通（liantong）= 动：经门，由一空间通达另一空间。回答"怎么走"。
//
// 归属原则：**能归属到某一进院的，归该院；归属不到任何一进院的，归域（根）**。
//   · 垂花门：独立门屋，建于院际卡子墙正中，两侧院都不独享 → 无归属 → 归域。
//   · 穿堂：上一进正房「明间前后贯通」的做法，属那座正房 → 属上一进院。
//   · 宅门：嵌于首院南界倒座房、不跨院 → 归首院。
//
// 门（gate）：**凡门皆立节点**，统一 schema、两种 kind ——
//   · kind:"gatehouse" 门屋：独立门屋或嵌墙门屋（宅门 / 垂花门 / 后门）。
//   · kind:"door"      门洞：房上明间门洞（倒座房门 / 厢房门 / 正房南北门）。
//   统一字段：
//     id        门屋 G:<院id>:<role>；门洞 G:<宿主建筑id>:door（一房多门追加 :s / :n）
//     kind      "gatehouse" | "door"
//     role      命名词条（zhaimen / chuihuamen / houmen / men）
//     host      所嵌/所属建筑的节点 id（垂花门嵌卡子墙 → null）
//     hostRole  宿主建筑的 role（供渲染拼「东厢房门」这类名字；前端不另存中文词表）
//     side      所在方位（bei / nan / dong / xi）
//     belongsTo zucheng 归属节点 id（院 / 域 / 宿主建筑）
//     between   分界的两院 id（垂花门用；布局据此定位到两院之间）
//     ways      liantong 边 [from, to, note] —— **由声明生成**，不再各处手写
//
// 墙（外围围墙/卡子墙）不立节点：某侧无建筑只是"那侧是围墙"，写成院落节点的边界属性。
// 图谱没声明的实体一律不画（忠实投影，不替图谱补想象）。
// ---------------------------------------------------------------------------

/* 两类关系：zucheng = 包含（静·骨架），liantong = 联通（动·动线）。 */
export const RELS = [
  { rel: "zucheng", label: "包含", desc: "静态组织：域 ⊃ 院落 ⊃ 建筑/门/附属" },
  { rel: "liantong", label: "联通", desc: "动态组织（动线）：经门，由一空间通达另一空间" },
];
const REL_SET = new Set(RELS.map((r) => r.rel));

export const SIDE_TAG = { nan: "南", bei: "北", dong: "东", xi: "西" };
const roleOf = (o) => (o && o.role) || null;

/* 一侧的界：优先用图谱层声明的 ring；无 ring（手写/旧版图谱）时按 enclosure 兜底。 */
function sideInfo(court, side, isSouthmost) {
  const e = (court.enclosure || {})[side] || {};
  const base = {
    role: roleOf(e),
    miankuo: e.miankuo ?? null,
    jinshen: e.jinshen ?? null,
    // 实体属性：图谱里本来就有（enclosure 各侧带），一路原样带到节点上，供 tooltip 展示。
    // 中文名一律由字典查（qingzhuan→青砖砌 / sandeng→三等·配房），前端不另存词表。
    height: e.height ?? null,
    taiming: e.taiming ?? null,
    level: e.level ?? null,
    material: e.material ?? null,
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
  if (side === "bei" && enc.beimen) gate = roleOf(enc.beimen);
  else if (side === "nan" && enc.nanmen) gate = roleOf(enc.nanmen);
  else if (side === "nan" && isSouthmost && e.gate) gate = roleOf(e.gate) || "zhaimen";
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
    const si = typeof s === "string" ? s : (s && s.id);
    const ti = typeof t === "string" ? t : (t && t.id);
    if (!si || !ti || si === ti) return;
    if (!REL_SET.has(rel)) throw new Error(`未知关系类型：${rel}`);
    links.push({ source: si, target: ti, rel, note: note || "" });
  };

  /* —— 域 —— */
  const root = push({ id: "domain", cat: "domain", role: data.type || "instance", jin: data.jin });

  /* —— 院落：按中轴序列；域 ⊃ 院落（包含）。seq 供布局按进数排序 —— */
  const courtNodes = courts.map((c) => {
    const rs = (c.ring || {}).nan || {};
    const n = push({
      id: cid(c), cat: "court", role: roleOf(c.center) || "tingyuan",
      name: c.name || "", court: c, seq: c.sequence ?? 0, boundary: {},
      // 院落自身属性（图谱 data.courtyards[] 上就有，原样挂到节点）：
      //   courtRole = 院落角色（waiyuan 外院 / tingfangyuan 前堂 / neiyuan 主院 / houzhaoyuan 后罩院），
      //               进深比 courtDepthRatio 就是按它取值的；字典暂无此词条 → 前端回落显示原 key。
      //   relation  = 围合关系（weihe），与中轴/对称/序列同属 dict「关系」类目。
      //   perimeter = 该院四周是否有围合。
      courtRole: c.role || null,
      relation: (c.enclosure || {}).relation || null,
      perimeter: !!c.perimeter,
      // 南界入口：gate = 真门（宅门/垂花门）；thru = 经上一进正房明间穿堂
      entry: rs.gate ? { gate: rs.gate } : (rs.thru ? { thru: rs.thru } : null),
    });
    link(root, n, "zucheng");
    return n;
  });
  const nextCourt = (i) => (i + 1 < courtNodes.length ? courtNodes[i + 1] : null);

  /* —— 门：统一生成器。归属（zucheng）+ 通行（liantong）都在这里落一次，
     调用处只声明"这是什么门、嵌在哪、连通哪两端"。
     anchor = 包含边的起点：默认取归属节点；宅门/后门嵌在某座房上，
     包含边从**那座房**出发（短线），而归首院/末进院写在 belongsTo 属性里（tooltip 展示）——
     若让包含边直接连院，它会横穿同一单元里的另一道门。 —— */
  const gate = ({ id, kind, role, host, hostRole, side, belongsTo, between, ways, anchor }) => {
    const n = push({
      id, cat: "gate", kind, role, host: host || null, hostRole: hostRole || null,
      side: side || null, belongsTo, between: between || null,
    });
    link(anchor || belongsTo, n, "zucheng");
    for (const [a, b, note] of ways || []) link(a, b, "liantong", note);
    return n;
  };

  /* —— 围合建筑 + 其门 ——
     有建筑 → 建筑节点（包含于本院）；无建筑 → 该侧边界属性（墙），不立节点。 */
  const bnode = new Map();          // `${院id}:${side}` -> 建筑节点
  courts.forEach((c, i) => {
    const cn = courtNodes[i];
    const sides = ["bei", "dong", "xi"];
    if (i === 0) sides.push("nan");   // 首院南界 = 倒座房（宅门嵌其上）
    for (const side of sides) {
      const info = sideInfo(c, side, i === 0 && side === "nan");
      // 各侧围合做法一律记进 boundary（原先只记"无建筑"那侧，有建筑侧的 houyanqiang 被丢了）：
      //   有建筑 → 该建筑的**后檐墙**houyanqiang 便充当这一侧的院墙；
      //   无建筑 → weiqiang 外围围墙 / kaziqiang 卡子墙。
      if (info.kind) cn.boundary[side] = info.kind;
      if (!info.provider) continue;
      const bn = push({
        id: `B:${cid(c)}:${side}`, cat: "building", role: info.provider,
        side, info, court: c,
        encloses: `${SIDE_TAG[side]}面 · 围合第${c.sequence}进院`,
      });
      bnode.set(`${cid(c)}:${side}`, bn);
      link(cn, bn, "zucheng");

      if (side === "bei" && info.chuantang && nextCourt(i)) {
        // 穿堂正房：明间南北贯通，两端各一门，串成「院 —南门→ 正房 —北门→ 下院」。
        const fromName = c.name || `第${c.sequence}进`;
        const nc = nextCourt(i);
        const toName = nc.name || `第${nc.court.sequence}进`;
        gate({
          id: `${bn.id}:door:s`, kind: "door", role: "men",
          host: bn.id, hostRole: bn.role, side: "nan", belongsTo: bn.id,
          ways: [
            [cn.id, `${bn.id}:door:s`, "经正房·南门(明间)"],
            [`${bn.id}:door:s`, bn.id, "南门进正房"],
          ],
        });
        gate({
          id: `${bn.id}:door:n`, kind: "door", role: "men",
          host: bn.id, hostRole: bn.role, side: "bei", belongsTo: bn.id,
          ways: [
            [bn.id, `${bn.id}:door:n`, "出正房经北门"],
            [`${bn.id}:door:n`, nc.id, `经正房·北门(穿堂)达「${toName}」`],
          ],
        });
      } else if (info.door) {
        // 每座围合建筑朝院都开有明间门洞：门是「院 ↔ 房」这一趟的枢纽，单独立节点。
        gate({
          id: `${bn.id}:door`, kind: "door", role: "men",
          host: bn.id, hostRole: bn.role, side, belongsTo: bn.id,
          ways: [
            [cn.id, `${bn.id}:door`, `经${bn.role}明间门洞`],
            [`${bn.id}:door`, bn.id, `入${bn.role}明间`],
          ],
        });
      }
    }
  });

  /* —— 对称：同院东西同名建筑 → 节点属性（不另立边） —— */
  courts.forEach((c) => {
    const e = nodes.find((n) => n.id === `B:${cid(c)}:dong`);
    const w = nodes.find((n) => n.id === `B:${cid(c)}:xi`);
    if (e && w && e.cat === "building" && e.role === w.role) {
      e.mirror = w.role; w.mirror = e.role;
    }
  });

  /* —— 门屋：宅门 / 垂花门 / 后门 —— */
  if (courts.length) {
    const c0 = courts[0], cn0 = courtNodes[0];
    const s0 = sideInfo(c0, "nan", true);
    if (s0.gate) {
      // 宅门：嵌于首院南界倒座房（东端一间改门道），对外、不跨院 → 归属首院。
      gate({
        id: `G:${cid(c0)}:${s0.gate}`, kind: "gatehouse", role: s0.gate,
        host: `B:${cid(c0)}:nan`, hostRole: s0.provider, side: "nan",
        belongsTo: cn0.id, anchor: `B:${cid(c0)}:nan`,
        ways: [[`G:${cid(c0)}:${s0.gate}`, cn0.id, "街 ↔ 院（正门·坎宅巽门）"]],
      });
    }
  }
  for (let i = 1; i < courts.length; i++) {
    const s = sideInfo(courts[i], "nan", false);
    if (!s.gate) continue;
    // 垂花门：独立门屋，建于院际卡子墙正中，两侧院都不独享 → 归域根，记明分界哪两院。
    const pn = courts[i - 1].name || `第${courts[i - 1].sequence}进`;
    const cn2 = courts[i].name || `第${courts[i].sequence}进`;
    const note = `经垂花门：${pn} ↔ ${cn2}`;
    gate({
      id: `G:${cid(courts[i])}:${s.gate}`, kind: "gatehouse", role: s.gate,
      host: null, hostRole: null, side: "nan", belongsTo: root.id,
      between: [courtNodes[i - 1].id, courtNodes[i].id],
      ways: [
        [courtNodes[i - 1].id, `G:${cid(courts[i])}:${s.gate}`, note],
        [`G:${cid(courts[i])}:${s.gate}`, courtNodes[i].id, note],
      ],
    });
  }
  if (courts.length) {
    // 后门：嵌于末进北界后罩房的西北角，宅院通往北胡同的出口。嵌在谁身上就归谁所在的院。
    const cLast = courts[courts.length - 1];
    const cnL = courtNodes[courtNodes.length - 1];
    const nLast = sideInfo(cLast, "bei", false);
    if (nLast.gate === "houmen") {
      gate({
        id: `G:${cid(cLast)}:houmen`, kind: "gatehouse", role: "houmen",
        host: `B:${cid(cLast)}:bei`, hostRole: nLast.provider, side: "bei",
        belongsTo: cnL.id, anchor: `B:${cid(cLast)}:bei`,
        ways: [[`G:${cid(cLast)}:houmen`, cnL.id, "院 ↔ 北胡同（后门·西北角）"]],
      });
    }
  }

  /* —— 附属构件（影壁）：包含于本院（轻量节点） ——
     游廊当前不在 peripheral 中 → 不生成节点；留待加细节阶段讨论形制与归属后再出现。 */
  courts.forEach((c, i) => {
    (c.peripheral || []).forEach((p, j) => {
      const n = push({ id: `${cid(c)}.aux${j}`, cat: "aux", role: roleOf(p), court: c });
      link(courtNodes[i], n, "zucheng");
    });
  });

  return { nodes, links, rels: RELS, meta: (graph && graph.meta) || {} };
}
