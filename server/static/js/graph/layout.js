// BUILDING.WIKI · 图谱视图 · 布局（力导向）
// ---------------------------------------------------------------------------
// 节点摆在哪，完全由「它连了谁」决定 —— 这是关系图的定义，也是与方位图的最后一道分界：
// 这里没有方位力、没有南北约束，谁和谁有关系谁就靠得近。
//
// d3-force 的 velocity Verlet 模拟：link 当弹簧、charge 当斥力、collide 防重叠。
// 收敛后保留一个极小的 alphaTarget，让整张图维持低幅「呼吸」——
// 动态波动就是这一步的副产品，不需要另做动画层。
//
// 自适应：先在单位尺度跑一段测出包围盒，再把**力的尺度**和节点坐标一起缩放进画布。
// 只缩坐标、不缩力的话，力与尺度失配，收敛后立刻漂出画布（这一点必须成对改）。
//
// 预热一律用 simulation.tick(n) 同步跑 —— 它不派发事件，所以不会触发渲染，
// 首帧直接呈现已收敛的完整图谱，而不是让用户看着一团乱麻慢慢散开。
// ---------------------------------------------------------------------------
// 走相对路径而不是 importmap：d3-force 是自包含单文件（无内部裸 import），
// 相对路径能让浏览器与 Node 校验脚本引用**同一份真实模块**，不必为 Node 另配解析器。
import {
  forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation,
} from "../../vendor/d3-force.js";

/* 节点半径：域 > 院 > 建筑 > 门 > 附属。建筑另按面阔微调 —— 尺度在图上一眼可读。
   门（gate）比附属大一号：它是院落边界上的构件，要比影壁这类附属更能被看见。 */
const R = { domain: 34, court: 21, building: 15, gate: 13, aux: 10 };

export function radiusOf(n) {
  if (n.cat === "building") {
    const mk = (n.info || {}).miankuo;
    if (typeof mk === "number") return Math.max(13, Math.min(20, 12 + 1.4 * (mk - 3)));
  }
  return R[n.cat] || 14;
}

/* 包含关系的理想长度：只有一类关系，但按**被包含者的类别**再分档 —— 包含链越往下越紧凑。
   域→院 撑开骨架；院→建筑 收紧；附属（影壁）是院内部件，必须贴紧本院，否则斥力
   会把它甩到别院附近，连线就会骑跨到外院节点上（五进 1440x820 实测 5/5 稳定复现）。
   门归域，取中等：既与院拉开层次，又不至于飘远。 */
/* 联通边的距离沿用「同 target.cat 的包含距离」：它与包含边常常连的是同一对节点，
   两条边力若不一致就会互相拉扯。故此处只是兜底值，实际取用见 applyForces。 */
const LINK_DIST = { zucheng: 168, liantong: 168 };
const LINK_DIST_BY_CAT = { court: 210, gate: 150, building: 92, aux: 64, passage: 150 };

const CHARGE = {
  // gate 的斥力比同尺寸的 aux 大一截：门是全院的出入口，它若被别的建筑夹住，
  // 「院—门」那条连线就会从夹住它的建筑圆上碾过去（四进实测稳定 1 处）。
  // 把它推到院落 subtree 的外缘，连线也就自然绕开了。
  domain: -620, court: -380, building: -195, gate: -300, aux: -100,
};

const PAD = 30;          // 左右下内边距
/* 顶部额外留白：标题与退出按钮以浮层形式压在画布上（下沿约 53px）。
   不给它让位的话，图谱纵向贴边时工具栏就会压到圆点上 —— 实测 1024x640 顶部仅 49px，差 4px。 */
const PAD_TOP = PAD + 34;
/* 碰撞余量：标签排在圆点正下方，长标签（「东外围围墙」5 字 ≈ 65px）比圆点宽得多。
   碰撞只按圆算的话，节点挤在一起时标签就会互相压字 —— 实测 4 进（27 节点）即触发。
   故余量取到能盖住常见标签的半宽，让 collide 顺带把标签空间一并撑开。 */
const COLLIDE_PAD = 34;

function applyForces(sim, links, k, box) {
  const cx = (box.x0 + box.x1) / 2, cy = (box.y0 + box.y1) / 2;   // 可用区域的中心
  sim.force("link", forceLink(links).id((d) => d.id)
    .distance((l) => ((l.target && LINK_DIST_BY_CAT[l.target.cat]) || LINK_DIST[l.rel] || 90) * k)
    // 联通边的弹簧力减到约三成：它与包含边常连同一对节点，力若等强，这一对会被拽得过紧、
    // 把骨架的层次挤没。动线是叠加在静之上的「用途」，不该改写静的间距。
    .strength((l) => (l.rel === "liantong" ? 0.26 : 0.72)));
  sim.force("charge", forceManyBody()
    .strength((d) => (CHARGE[d.cat] || -150) * k * k)
    .distanceMax(900 * k));
  sim.force("collide", forceCollide()
    .radius((d) => (radiusOf(d) + COLLIDE_PAD) * k)
    // 3 次而非 2：加了动线之后同对节点间常有两层关系，节点更密；迭代少一轮就压不住
    // 「院—门」这类新连线从别的建筑圆上碾过去（四进 1280x820 实测 1 处骑跨）。
    .iterations(3));
  sim.force("center", forceCenter(cx, cy));
}

function extent(nodes) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of nodes) {
    const r = radiusOf(n) + COLLIDE_PAD;
    x0 = Math.min(x0, n.x - r); x1 = Math.max(x1, n.x + r);
    y0 = Math.min(y0, n.y - r); y1 = Math.max(y1, n.y + r);
  }
  return { w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0), cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
}

function scaleInto(nodes, e, s) {
  for (const n of nodes) {
    n.x = e.cx + (n.x - e.cx) * s;
    n.y = e.cy + (n.y - e.cy) * s;
    n.vx *= s; n.vy *= s;
  }
}

export function createLayout(model, W, H) {
  const nodes = model.nodes.map((n) => ({ ...n }));
  const links = model.links.map((l) => ({ ...l }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  for (const l of links) {                     // d3 会把 source/target 就地换成节点对象
    l.source = byId.get(l.source) || l.source;
    l.target = byId.get(l.target) || l.target;
  }

  const cx0 = (PAD + (W - PAD)) / 2, cy0 = (PAD_TOP + (H - PAD)) / 2;   // 画布可用区中心

  /* 初始布局：域置中，各院按 sequence 绕域均匀排布。
     纯力导向在节点变多时会把某个院的子树甩到「域→另一院」的连线上 —— 五进实测
     5/5 稳定复现（domain→cy2 的边穿过第 5 进的建筑圆）。给院一个按次序的径向初值，
     力导向就从「不缠绕」的构型出发收敛：既是几何修正，也让「第几进」在图上按角度可读。 */
  const dom = nodes.find((n) => n.cat === "domain");
  if (dom) { dom.x = cx0; dom.y = cy0; }
  const courts = nodes.filter((n) => n.cat === "court")
    .sort((a, b) => ((a.court && a.court.sequence) || 0) - ((b.court && b.court.sequence) || 0));
  courts.forEach((n, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(1, courts.length);
    n.x = cx0 + Math.cos(ang) * LINK_DIST_BY_CAT.court;
    n.y = cy0 + Math.sin(ang) * LINK_DIST_BY_CAT.court;
  });
  /* 其余节点：绕各自的父节点按索引均匀分散。兄弟若挤在同一侧，「父→兄」的连线就会
     从弟的圆上碾过去（一进 1024x640 实测：宅门连线穿过影壁圆，d=1.3 / r=10）。 */
  const kidsOf = new Map();
  for (const l of links) {
    if (l.target.x != null) continue;                  // 已在上一步定过初值的不再动
    if (!kidsOf.has(l.source.id)) kidsOf.set(l.source.id, []);
    kidsOf.get(l.source.id).push(l.target);
  }
  for (const [pid, kids] of kidsOf) {
    const p = byId.get(pid);
    if (!p || p.x == null) continue;
    kids.forEach((n, i) => {
      const ang = -Math.PI / 2 + (2 * Math.PI * i) / kids.length;
      const r = LINK_DIST_BY_CAT[n.cat] || LINK_DIST.zucheng;
      n.x = p.x + Math.cos(ang) * r;
      n.y = p.y + Math.sin(ang) * r;
    });
  }

  /* 嵌于建筑的门（宅门嵌倒座房 / 各房的明间门洞 / 后门嵌后罩房）：初值贴到它**所嵌的那座房子**旁，
     而不是只跟着院——只跟着院的话，力导向会把门甩到「院—另一座建筑」的连线上
     （三进 1024x640、四进 1280x820 实测：后罩院→后门 的线碾过厢房圆）。
     注：这只是**布局初值**，力导向仍会重排；side 取自图谱的边界声明，图上不声称方位。
     host 即数据层的门.host（所嵌建筑节点 id），与 model.js 的门 schema 同源。 */
  for (const n of nodes) {
    if (!n.host) continue;
    const h = byId.get(n.host);
    if (!h || h.x == null) continue;
    const ang = n.side === "bei" ? -Math.PI / 2 : Math.PI / 2;
    const rr = radiusOf(h) + radiusOf(n) + 26;
    n.x = h.x + Math.cos(ang) * rr;
    n.y = h.y + Math.sin(ang) * rr;
  }

  const sim = forceSimulation(nodes)
    .alphaDecay(0.014)
    .velocityDecay(0.36)
    .stop();

  /* 可用区域：左右下留画布边距，顶部额外让出工具栏高度（它是浮层，压在画布上） */
  const box = { x0: PAD, y0: PAD_TOP, x1: W - PAD, y1: H - PAD };
  const bw = box.x1 - box.x0, bh = box.y1 - box.y0;
  const cx = (box.x0 + box.x1) / 2, cy = (box.y0 + box.y1) / 2;

  let k = 1;
  applyForces(sim, links, k, box);

  // 迭代 fit：跑一段 → 量包围盒 → 尺度与坐标一起缩 → 重跑，把布局填进画布（通常 2 轮即稳）
  sim.tick(45);
  for (let pass = 0; pass < 3; pass++) {
    const e = extent(nodes);
    const k2 = Math.min(bw / e.w, bh / e.h);
    if (k2 <= 1.2 && k2 >= 0.83) break;
    k *= k2;
    scaleInto(nodes, e, k2);
    applyForces(sim, links, k, box);
    sim.alpha(0.9);
    sim.tick(220);
  }

  sim.alpha(1);                                 // 在最终尺度上让布局彻底落定
  sim.tick(160);

  /* 收尾 fit —— 必须放在**所有** tick 之后。上面那次高能重排会把布局重新摊开，
     fit 若排在它前面，结果立刻被推翻（实测正是因此有圆点溢出画布）。
     extent 用的是「半径 + COLLIDE_PAD」，比圆点本身宽 17px，
     余量正好吸收随后微动模式的低幅游移，故此后不会再越界。 */
  const eFit = extent(nodes);
  const kFit = Math.min(bw / eFit.w, bh / eFit.h);
  k *= kFit;
  scaleInto(nodes, eFit, kFit);
  for (const n of nodes) { n.x += cx - eFit.cx; n.y += cy - eFit.cy; }
  applyForces(sim, links, k, box);

  /* 进入微动模式：alphaTarget 极小 → sqrt(alpha) 保持可感，整张图长期缓慢游动。
     velocityDecay 比收敛期小，速度不会被早早磨平，于是"波动"是连续的而非一闪即逝。 */
  sim.velocityDecay(0.42).alpha(0.06).alphaTarget(0.006);

  return {
    simulation: sim,
    nodes,
    links,
    radiusOf,
    start() { sim.restart(); return this; },
    stop() { sim.stop(); return this; },
    /* 拖拽：按住时把节点钉在指针上并升温，松开即释放 —— 力会自然把整张图重新摊开 */
    pin(node, x, y) {
      node.fx = x; node.fy = y;
      sim.alphaTarget(0.28).restart();
    },
    unpin(node) {
      node.fx = null; node.fy = null;
      sim.alphaTarget(0.006);
    },
  };
}

export { LINK_DIST, PAD };
