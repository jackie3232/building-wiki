// BUILDING.WIKI · 根节点附属数据面板
// ---------------------------------------------------------------------------
// 三块附加数据都挂在四合院根节点上（见 model.js 的 buildModel）：
//   meta  元信息 —— 这张图是什么、谁生成的、是不是零坐标
//   rules 规则   —— appliedRules.norms 快照（模数 / 院深比 / 墙厚 / 门宽…本实例用到的）
//   dict  字典   —— appliedDict（本实例用到的命名字典子集，拼音 key ↔ 中文名）
//
// 打开方式：**点击**根节点（不是悬停 —— 这三块几十行，tooltip 装不下）。
// 收合：右上 × · Esc。只读：不改图谱、不落盘、不触发布局。
// 键名优先走命名字典中文名；全典里没有该词条的，原样显示 key ——
// 不为 meta / norms 的英文键另造一张前端词表。
// ---------------------------------------------------------------------------

let current = null;

function el(tag, cls, txt) {
  const d = document.createElement(tag);
  if (cls) d.className = cls;
  if (txt != null) d.textContent = txt;
  return d;
}

const isPlain = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

/* 标量原样；数组顿号连；对象折成「k v · k v」一行预览（**跳过 desc** —— 释义单独成行，
   混进数值预览会把一行动辄撑成几百字） */
function flat(v) {
  if (v == null) return "—";
  if (typeof v !== "object") return String(v);
  if (Array.isArray(v)) return v.map(flat).join("、");
  const ks = Object.entries(v).filter(([k]) => k !== "desc");
  return ks.map(([k, x]) => `${k} ${flat(x)}`).join(" · ") || "—";
}

/* key 行：字典有词条就给中文名 + 拼音原 key（对得上数据里的字段），没有就原样 */
function keyOf(r, key, dict) {
  const hit = dict[key];
  r.append(el("span", "ga-key", hit ? hit.label : key));
  if (hit && hit.label !== key) r.append(el("span", "ga-pin", key));
}

/* 填一行；返回「是否还要铺一层子行」。
   顶层对象 → 报子项数并展开一层；子层对象 → 折成一行预览（跳过 desc，否则一行会被撑到几百字）；
   长文本（desc 或 40 字以上）→ 单独占一行小字，不挤数值列。 */
function cells(r, key, val, dict, top) {
  keyOf(r, key, dict);
  if (isPlain(val)) {
    if (top) { r.append(el("span", "ga-cnt", `${Object.keys(val).length} 项`)); return true; }
    r.append(el("span", "ga-val", flat(val)));
    return false;
  }
  if (typeof val === "string" && (key === "desc" || val.length > 40)) r.append(el("span", "ga-desc", val));
  else r.append(el("span", "ga-val", flat(val)));
  return false;
}

/* k-v 列表：顶层对象缩进展开一层，再深折成一行预览（面板不下钻无限层） */
function rows(host, obj, dict) {
  for (const [k, v] of Object.entries(obj)) {
    const r = el("div", "ga-row");
    const deeper = cells(r, k, v, dict, true);
    host.append(r);
    if (!deeper) continue;
    const sub = el("div", "ga-sub");
    for (const [sk, sv] of Object.entries(v)) {
      const sr = el("div", "ga-row");
      cells(sr, sk, sv, dict, false);
      sub.append(sr);
    }
    host.append(sub);
  }
}

function section(title, note, open) {
  const s = el("section", "ga-sec" + (open ? " is-open" : ""));
  const h = el("button", "ga-sec-head");
  h.type = "button";
  h.append(el("span", "ga-caret"), el("span", "ga-sec-title", title),
           el("span", "ga-sec-note", note));
  const body = el("div", "ga-sec-body");
  h.addEventListener("click", () => s.classList.toggle("is-open"));
  s.append(h, body);
  return { s, body };
}

function build(node, dict) {
  const root = el("div", "ga-panel");

  const head = el("div", "ga-head");
  const nm = dict[node.role] ? dict[node.role].label : (node.role || "实例");
  head.append(el("span", "ga-title", `${nm} · 附属数据`));
  const x = el("button", "ga-close", "×");
  x.type = "button";
  x.title = "收起（Esc）";
  x.addEventListener("click", () => closeAttached());
  head.append(x);

  const body = el("div", "ga-body");

  /* ① 元信息 */
  const meta = node.meta || {};
  const s1 = section("元信息", `meta · ${Object.keys(meta).length} 项`, true);
  rows(s1.body, meta, dict);

  /* ② 规则：appliedRules.norms */
  const rules = node.rules || {};
  const s2 = section("规则", `appliedRules · ${Object.keys(rules).length} 项`, true);
  rows(s2.body, rules, dict);

  /* ③ 字典：appliedDict，按类目分组（meta 段是类别说明、不是词条，跳过） */
  const d = node.dict || {};
  const cats = Object.entries(d).filter(([k, v]) => k !== "meta" && isPlain(v));
  const cnt = cats.reduce((a, [, v]) => a + Object.keys(v).length, 0);
  const s3 = section("字典", `appliedDict · ${cnt} 词条`, false);
  for (const [cat, items] of cats) {
    const ks = Object.keys(items);
    if (!ks.length) continue;
    s3.body.append(el("div", "ga-cat", `${cat} · ${ks.length}`));
    const wrap = el("div", "ga-catbody");
    for (const [k, v] of Object.entries(items)) {
      const r = el("div", "ga-row");
      r.append(el("span", "ga-key", (v && v.label) || k));
      r.append(el("span", "ga-pin", k));
      if (v && v.desc) r.append(el("span", "ga-desc", v.desc));
      wrap.append(r);
    }
    s3.body.append(wrap);
  }

  body.append(s1.s, s2.s, s3.s);
  root.append(head, body);
  return root;
}

export function closeAttached() {
  const host = document.getElementById("graph-attached");
  if (host) { host.classList.remove("is-open"); host.replaceChildren(); }
  current = null;
}

export function toggleAttached(node, dict) {
  const host = document.getElementById("graph-attached");
  if (!host || !node) return;
  if (current === node && host.classList.contains("is-open")) { closeAttached(); return; }
  host.replaceChildren(build(node, dict || {}));
  host.classList.add("is-open");
  current = node;
}

/* Esc 先收面板，其次才是退出图谱视图 —— 故在捕获阶段拦截并止住冒泡 */
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const host = document.getElementById("graph-attached");
  if (!host || !host.classList.contains("is-open")) return;
  e.stopPropagation();
  e.preventDefault();
  closeAttached();
}, true);
