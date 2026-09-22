#!/usr/bin/env node
/**
 * BUILDING.WIKI · 智能化层 · 装配器（Agent 原生 / Node）
 * ============================================================
 * 职责：LLM 骨架（纯 role + 业务量） -> 自包含实例图谱。
 *
 * 这是 server/engine/geometry.py 里 assemble_instance 及其装配段的
 * **忠实移植**（同一契约、同一产物）。移植目标不是「把 Python 搬过来」，
 * 而是让智能化层以 Agent 的原生形态存在（Agent 运行时 = @anthropic-ai/claude-agent-sdk / Node）。
 *
 * 分层依据（geometry.py L1-8 / L424-428）：
 *   - 装配 = 查表 + 拓扑，**零推理**；产物是**语义结构**（图谱），不是几何。
 *   - 数字在这里角色是「知识的搬运/快照」：把知识中心的 norms 原样抄进图谱，
 *     不运算、不出坐标。→ 因此装配属**智能化**，不属自动化（④⑤）。
 *   - 故本脚本与知识中心同在 Agent 侧；MCP 面只有 ④⑤。
 *
 * 红线（§13.4#1，2026-09-22 收窄）：LLM 不得接触**坐标 / 几何量**
 * （坐标、朝向、镜像、法向量，以及「由尺寸推坐标」的运算）——「不碰数字」指的是
 * 几何量，**不是所有数字**。骨架 = role + 拓扑（+ 可选业务量，值域取自知识中心）；
 * 面阔/进深/高/台明/等级/材质由本脚本查知识中心补。
 *
 * 用法：
 *   node assemble.mjs --knowledge <dir> --skeleton <file.json>   # 输出图谱 JSON 到 stdout
 *   或： cat skeleton.json | node assemble.mjs --knowledge <dir>
 *   默认 --knowledge 取脚本同目录下的 ./knowledge。
 *
 * 零漂移：与 Python assemble_instance 逐字段深比对（见 _verify_port.py）。
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));

// 骨架里允许携带的建筑声明字段（与 Python geometry._ROOM_DECL_KEYS 一致）：
// 声明性的（门 / 穿堂）+ 业务量（面阔…）。业务量的值域由 rules.paramRanges 约束（见 validatePlan）。
const ROOM_DECL_KEYS = ["gate", "chuantang", "miankuo"];

// ④ 实际消费的 norms 路径前缀（与 Python _NORMS_KEEP_PREFIXES 一致）
const NORMS_KEEP_PREFIXES = [
  ["modus"], ["courtDepthRatio"],
  ["room"], ["door"], ["zhaimen"], ["houmen"], ["layout"], ["chuihuamen"],
  ["peripheral"], ["wall"],
  ["zhengfang"], ["xiangfang"], ["daozuofang"], ["houzhaofang"],
];

const CN_NUM = { 1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十" };

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}

// ---------------- 知识中心 ----------------

/** 读知识中心三件套（rules / type / dict）。与 Python _load_knowledge 同契约。 */
function loadKnowledge(dir) {
  return {
    rules: loadJson(path.join(dir, "siheyuan.rules")),
    type: loadJson(path.join(dir, "siheyuan.type.json")),
    dict: loadJson(path.join(dir, "dict.json")),
  };
}

// ---------------- 规则快照 ----------------

/** 从 norms 取 prefix 路径下的整棵子树；任一节点缺失返回 null。 */
function keepSubtree(src, prefix) {
  let cur = src;
  for (const k of prefix) {
    if (cur === null || typeof cur !== "object" || Array.isArray(cur) || !(k in cur)) return null;
    cur = cur[k];
  }
  return cur;
}

/** 规则库 -> appliedRules 快照：只保留 ④ 实际消费的 norms 子树，无关词条全裁。 */
function snapshotRules(rulesDoc) {
  const full = rulesDoc?.norms ?? {};
  if (full === null || typeof full !== "object" || Array.isArray(full) || !("modus" in full)) {
    throw new Error("图谱缺陷：siheyuan.rules 缺少 norms.modus");
  }
  const trimmed = {};
  for (const prefix of NORMS_KEEP_PREFIXES) {
    const sub = keepSubtree(full, prefix);
    if (sub === null) continue;
    let d = trimmed;
    for (const k of prefix.slice(0, -1)) {
      if (!(k in d)) d[k] = {};
      d = d[k];
    }
    d[prefix[prefix.length - 1]] = sub;
  }
  return { norms: trimmed };
}

// ---------------- 命名字典裁剪 ----------------

/** 收集若干图谱块里出现过的全部标量字符串值。 */
function usedTerms(...docs) {
  const used = new Set();
  const walk = (o) => {
    if (Array.isArray(o)) { for (const v of o) walk(v); }
    else if (o !== null && typeof o === "object") { for (const v of Object.values(o)) walk(v); }
    else if (typeof o === "string") { used.add(o); }
  };
  for (const d of docs) walk(d);
  return used;
}

/** 命名字典子集：只保留被用到的词条（按类别裁剪）；meta 段整段保留。 */
function extractDict(dictDoc, ...docs) {
  if (!dictDoc) return null;
  const used = usedTerms(...docs);
  const out = {};
  for (const [cat, entries] of Object.entries(dictDoc)) {
    if (cat === "meta" || entries === null || typeof entries !== "object" || Array.isArray(entries)) {
      out[cat] = entries;
      continue;
    }
    const keep = {};
    for (const [k, v] of Object.entries(entries)) if (used.has(k)) keep[k] = v;
    if (Object.keys(keep).length) out[cat] = keep;
  }
  return out;
}

// ---------------- 装配 ----------------

/** 一栋建筑的声明：role + 尺度 + 该栋自身属性（等级/材质/高度/台明）。与 Python _room 同形。 */
function room(role, norms, typeDoc) {
  const n = norms?.[role] ?? {};
  const t = typeDoc?.roles?.[role] ?? {};
  const r = {
    role,
    miankuo: n.miankuo !== undefined ? n.miankuo : 5,
    jinshen: n.jinshen !== undefined ? n.jinshen : 3,
    // 朝院门洞：各房门窗均向院内开辟，门在明间(正中开间)。
    // 开向不进图谱——由房屋所在侧推得，属几何事实；写进图谱就变成引擎级动作了。
    door: { at: "mingjian" },
  };
  for (const k of ["height", "taiming"]) if (n[k] !== undefined && n[k] !== null) r[k] = n[k];
  for (const k of ["level", "material"]) if (t[k] !== undefined && t[k] !== null) r[k] = t[k];
  return r;
}

/** 骨架里的建筑声明 -> 完整建筑：role 查表补全尺度/等级/材质，声明字段原样合上。 */
function expandRoom(spec, norms, typeDoc) {
  if (spec === null || typeof spec !== "object" || Array.isArray(spec) || !spec.role) {
    throw new Error(`图谱缺陷：骨架中的建筑声明缺 role：${JSON.stringify(spec)}`);
  }
  const r = room(spec.role, norms, typeDoc);
  for (const k of ROOM_DECL_KEYS) if (k in spec) r[k] = spec[k];
  return r;
}

// ---------------- 第一级合法性闸（词表 + 值域 + 结构） ----------------
// 与 Python 侧 understanding._validate / _check_room / _legal_roles 同契约：
// 这是**理解层产物**的准入检查，不是几何校验。任何一项不过即抛错——不静默放行。
// 值域取自知识中心 rules.paramRanges：真值域是知识中心的一个旋钮，改域不改码。

const SIDES = ["bei", "nan", "dong", "xi"];

/** 合法 role 集 = 类型图谱 roles ∪ 命名字典「空间角色」。 */
function legalRoles(typeDoc, dictDoc) {
  const roles = new Set(Object.keys(typeDoc?.roles ?? {}));
  for (const k of Object.keys(dictDoc?.["空间角色"] ?? {})) roles.add(k);
  return roles;
}

/** 单栋建筑声明校验：role 须在词表内（否则是幻觉节点）；gate.role 同检；声明字段白名单 + 业务量值域。 */
function checkRoom(spec, roles, rules, where) {
  if (spec === null || typeof spec !== "object" || Array.isArray(spec)) {
    throw new Error(`图谱缺陷：${where} 不是对象`);
  }
  if (!roles.has(spec.role)) {
    throw new Error(`图谱缺陷：${where} 的 role=${JSON.stringify(spec.role)} 不在合法词表（幻觉节点）`);
  }
  const gate = spec.gate;
  if (gate !== null && gate !== undefined) {
    if (typeof gate !== "object" || Array.isArray(gate) || !roles.has(gate.role)) {
      throw new Error(`图谱缺陷：${where} 的 gate.role=${JSON.stringify(gate?.role)} 不在合法词表`);
    }
  }
  // 声明字段白名单 + 业务量值域（业务量的域取自 rules.paramRanges）
  const ranges = rules?.paramRanges ?? {};
  for (const key of Object.keys(spec)) {
    if (key === "role") continue;
    if (!ROOM_DECL_KEYS.includes(key)) {
      throw new Error(`图谱缺陷：${where} 出现不可声明的字段「${key}」（骨架只允许 role + ${ROOM_DECL_KEYS.join(" / ")}）`);
    }
    const entry = ranges[key];
    if (entry === undefined) continue;               // gate / chuantang 等：非业务量，无值域
    const v = spec[key];
    if (!Number.isInteger(v)) {
      throw new Error(`图谱缺陷：${where}.${key}=${JSON.stringify(v)} 不是整数`);
    }
    const rng = entry.range;
    if (!Array.isArray(rng) || rng.length !== 2) {
      throw new Error(`图谱缺陷：paramRanges.${key} 缺少 range（值域未声明）`);
    }
    const [lo, hi] = rng;
    const step = Number.isInteger(entry.step) && entry.step > 0 ? entry.step : 1;
    if (v < lo || v > hi || (v - lo) % step !== 0) {
      throw new Error(`图谱缺陷：${where}.${key}=${v} 不在知识中心声明值域 ${lo}-${hi}（步长 ${step}）`);
    }
  }
}

/** 第一级合法性闸：plan 必须词表内、值域内、结构完整。返回 plan（便于串联）。 */
function validatePlan(plan, { rules, type, dict }) {
  if (plan === null || typeof plan !== "object" || Array.isArray(plan)) {
    throw new Error("图谱缺陷：理解层产物不是对象");
  }
  const specs = plan.courtyards;
  if (!Array.isArray(specs) || specs.length === 0) {
    throw new Error("图谱缺陷：courtyards 缺失或为空");
  }
  const jin = Number(plan.jin);
  if (!Number.isInteger(jin)) {
    throw new Error(`图谱缺陷：jin 不是整数：${JSON.stringify(plan.jin)}`);
  }
  const rng = rules?.paramRanges?.jin?.range;
  if (!Array.isArray(rng) || rng.length !== 2) {
    throw new Error("图谱缺陷：siheyuan.rules 缺少 paramRanges.jin.range（值域未声明）");
  }
  const [lo, hi] = rng;
  if (jin < lo || jin > hi) {
    throw new Error(`图谱缺陷：jin=${jin} 超出知识中心声明值域 ${lo}-${hi}`);
  }
  if (specs.length !== jin) {
    throw new Error(`图谱缺陷：jin=${jin} 与 courtyards 数量 ${specs.length} 不符`);
  }
  const roles = legalRoles(type, dict);
  const seen = new Set();
  specs.forEach((spec, i) => {
    if (spec === null || typeof spec !== "object" || Array.isArray(spec)) {
      throw new Error(`图谱缺陷：courtyards[${i}] 不是对象`);
    }
    const seq = Number(spec.sequence);
    if (!Number.isInteger(seq) || seq < 1 || seq > jin) {
      throw new Error(`图谱缺陷：courtyards[${i}].sequence=${JSON.stringify(spec.sequence)} 非法`);
    }
    if (seen.has(seq)) throw new Error(`图谱缺陷：sequence ${seq} 重复`);
    seen.add(seq);
    const enc = spec.enclosure;
    if (enc === null || typeof enc !== "object" || Array.isArray(enc)) {
      throw new Error(`图谱缺陷：courtyards[${i}].enclosure 缺失`);
    }
    for (const side of SIDES) {
      if (enc[side] !== null && enc[side] !== undefined) {
        checkRoom(enc[side], roles, rules, `courtyards[${i}].enclosure.${side}`);
      }
    }
    for (const k of ["beimen", "nanmen"]) {
      if (enc[k] !== null && typeof enc[k] === "object" && !Array.isArray(enc[k])) {
        checkRoom(enc[k], roles, rules, `courtyards[${i}].enclosure.${k}`);
      }
    }
    const per = spec.peripheral ?? [];
    if (!Array.isArray(per)) throw new Error(`图谱缺陷：courtyards[${i}].peripheral 不是数组`);
    per.forEach((p, j) => checkRoom(p, roles, rules, `courtyards[${i}].peripheral[${j}]`));
  });
  if (seen.size !== jin) {
    throw new Error(`图谱缺陷：sequence 未覆盖 1..${jin}`);
  }
  return plan;
}

/** 院名解析器：court_name(k, jin) -> 中文院名。事实源 = rules.sequence.naming。 */
function courtNamer(rulesDoc, dictDoc) {
  const naming = rulesDoc?.sequence?.naming ?? {};
  const rules = naming.rules ?? [];
  const fallback = naming.fallback ?? {};
  if (!rules.length || !Object.keys(fallback).length) {
    throw new Error("图谱缺陷：siheyuan.rules 缺少 sequence.naming.rules / .fallback");
  }
  const lbl = (key) => {
    for (const cat of ["院落", "空间角色"]) {
      const v = dictDoc?.[cat]?.[key];
      if (v !== null && typeof v === "object" && typeof v.label === "string") return v.label;
    }
    throw new Error(`图谱缺陷：院名 key「${key}」在命名字典「院落/空间角色」中无 label`);
  };
  return function courtName(k, jin) {
    for (const r of rules) {
      const at = r.at;
      if (at === "last") { if (k !== jin) continue; }
      else if (at !== k) continue;
      if ("jinEq" in r && jin !== r.jinEq) continue;
      if ("jinGte" in r && jin < r.jinGte) continue;
      return lbl(r.name);
    }
    const n = k - (fallback.ordinalFrom ?? 2);
    if (n < 2) {
      throw new Error(
        `图谱缺陷：第 ${k} 进（共 ${jin} 进）在 sequence.naming 中无规则命中，` +
        `且不满足 fallback 序数（序数算出为 ${n}）`);
    }
    return `${lbl(fallback.name)}·${CN_NUM[n] !== undefined ? CN_NUM[n] : String(n)}`;
  };
}

const roleOf = (obj, dflt = null) =>
  obj !== null && typeof obj === "object" && !Array.isArray(obj) ? (obj.role ?? dflt) : dflt;

/** 规则库里 `when` 条件的求值（如 "jin>=4" / "jin==2" / null=恒真）。 */
function jinCondOk(cond, jin) {
  if (!cond) return true;
  const m = /^\s*jin\s*(>=|<=|==|>|<)\s*(\d+)\s*$/.exec(String(cond));
  if (!m) throw new Error(`图谱缺陷：rules 中无法求值的 when 条件「${cond}」`);
  const op = m[1], n = parseInt(m[2], 10);
  return { ">=": jin >= n, "<=": jin <= n, "==": jin === n, ">": jin > n, "<": jin < n }[op];
}

/** 装配收尾：omit 裁剪 -> usage 标注 -> 院角色判定 -> ring 声明 -> 打包附属知识。纯机械，零推理。 */
function finish(jin, courtyards, rulesDoc, dictDoc, omit = null) {
  const omitSet = new Set(omit ?? []);
  for (const c of courtyards) {
    const enc = c.enclosure ?? {};
    for (const side of ["bei", "nan", "dong", "xi"]) {
      const role = roleOf(enc[side], null);
      if (role && omitSet.has(`${role}_${side}`)) enc[side] = null;
    }
  }

  // 用途(usage)：图谱声明「某角色在某情形下作何用途」——如四进院第二进院正位房作过厅。
  for (const u of rulesDoc?.usage ?? []) {
    const uRole = u.role, uUse = u.usage, uAt = u.at, uCond = u.when;
    if (!uRole || !uUse || !uAt || !jinCondOk(uCond, jin)) continue;
    if (uAt === "erjinyuan_zhengwei") {
      const target = courtyards.length > 1 ? (courtyards[1].enclosure ?? {}) : {};
      const nm = target.bei;
      if (nm && nm.role === uRole) nm.usage = uUse;
    }
  }

  // 标注每进角色(waiyuan/neiyuan/houzhaoyuan)，对齐自然语言「外院/内院/后罩院」层级描述
  let neiyuanIdx = null;
  for (let i = 0; i < courtyards.length; i++) {
    const bei = courtyards[i].enclosure?.bei ?? {};
    if (bei.role === "zhengfang" && bei.usage !== "guoting") { neiyuanIdx = i; break; }
  }
  for (let i = 0; i < courtyards.length; i++) {
    const c = courtyards[i];
    if (neiyuanIdx === null || i === neiyuanIdx) {
      c.role = courtyards.length === 1 ? "tingyuan" : "neiyuan";
    } else if (i < neiyuanIdx) {
      const bei = c.enclosure?.bei ?? {};
      c.role = bei.usage === "guoting" ? "tingfangyuan" : "waiyuan";
    } else {
      c.role = "houzhaoyuan";
    }
  }

  // 图谱层显式声明 ring：每侧墙基底 + provider（被谁后檐墙分段实现）+ gate（零坐标·语义·可逆）。
  for (let i = 0; i < courtyards.length; i++) {
    const c = courtyards[i];
    const enc = c.enclosure ?? {};
    const nr = roleOf(enc.bei, null);
    const sr = roleOf(enc.nan, null);
    const er = roleOf(enc.dong, null);
    const wr = roleOf(enc.xi, null);
    const prevEnc = i > 0 ? (courtyards[i - 1].enclosure ?? {}) : {};
    const prevNr = roleOf(prevEnc.bei, null);

    let nProv, nKind, nGate;
    if (enc.beimen) {
      nProv = null; nKind = "kaziqiang"; nGate = "chuihuamen";
    } else {
      const ngate = enc.bei?.gate?.role ?? null;
      nProv = nr; nKind = nr ? "houyanqiang" : "weiqiang"; nGate = ngate;
    }

    let sProv, sKind, sGate, sThru;
    if (i === 0) {
      sProv = sr; sKind = sr ? "houyanqiang" : "weiqiang";
      sGate = enc.nan?.gate ? "zhaimen" : null;
      sThru = null;
    } else {
      sProv = prevNr; sKind = prevNr ? "houyanqiang" : "weiqiang";
      if (prevEnc.beimen) {
        sGate = "chuihuamen"; sThru = null;
      } else if (prevEnc.bei?.chuantang) {
        // 穿堂不是门：它是上一进北房「明间前后贯通」的做法，随正房归属上一进院。
        sGate = null;
        sThru = { via: "chuantang", of: prevNr, courtyard: courtyards[i - 1].name };
      } else {
        sGate = null; sThru = null;
      }
    }

    c.ring = {
      bei: { provider: nProv, kind: nKind, gate: nGate },
      nan: { provider: sProv, kind: sKind, gate: sGate, thru: sThru },
      dong: { provider: er, kind: er ? "houyanqiang" : "weiqiang" },
      xi: { provider: wr, kind: wr ? "houyanqiang" : "weiqiang" },
    };
  }

  return wrap(jin, courtyards, rulesDoc, dictDoc);
}

/** instance = data（实例图谱）+ appliedDict / appliedRules（用到的附属知识，知识中心的按需子集）。 */
function wrap(jin, courtyards, rulesDoc, dictDoc, generatedBy = "assemble.mjs (skill siheyuan)") {
  const data = { type: "siheyuan", jin, courtyards };
  const rulesSnap = snapshotRules(rulesDoc);
  const inst = {
    meta: {
      type: "siheyuan",
      desc: `北京${jin}进四合院实例（由类型图谱+规则库合成，工程文件·自包含）`,
      generatedBy,
      zeroCoord: true,
    },
    data,
    appliedRules: rulesSnap,
  };
  if (dictDoc !== null && dictDoc !== undefined) {
    inst.appliedDict = extractDict(dictDoc, data, rulesSnap);
  }
  return inst;
}

/**
 * ① 骨架 -> 自包含 instance（装配 = 查表 + 拓扑，零推理）。
 *
 * plan 形状（= 实例图谱 data 块的声明式压缩）：
 *   { "jin": 3, "courtyards": [ { "sequence": 1,
 *       "enclosure": { "nan": {"role":"daozuofang","gate":{"role":"zhaimen"}},
 *                      "beimen": {"role":"chuihuamen"} },
 *       "peripheral": [{"role":"yingbi"}], "perimeter": true }, ... ] }
 *
 * - 尺度数值由 expandRoom 查知识中心补；骨架只带 role / 拓扑 / jin（+ 可选业务量，如 miankuo）。
 * - 院名不取自骨架，由 sequence.naming 规则推导（命名权归图谱，不归 LLM）。
 * - 收尾与确定性基线共用 finish，故形状必然一致。
 */
export function assembleInstance(plan, knowledgeDir, opts = {}) {
  const { rules, type, dict } = loadKnowledge(knowledgeDir);
  const norms = rules.norms ?? {};
  const courtName = courtNamer(rules, dict);

  // 第一级合法性闸：词表 + 值域 + 结构。不过即抛错（调用方回落确定性基线）。
  validatePlan(plan, { rules, type, dict });
  const specs = plan.courtyards;
  const jin = Number(plan.jin);

  const courtyards = [];
  specs.forEach((spec, i) => {
    if (spec === null || typeof spec !== "object" || Array.isArray(spec)) {
      throw new Error(`图谱缺陷：courtyards[${i}] 不是对象`);
    }
    const seq = Number(spec.sequence || (i + 1));
    const encIn = spec.enclosure ?? {};
    const enc = { relation: encIn.relation || "weihe" };
    for (const side of ["bei", "nan", "dong", "xi"]) {
      if (encIn[side] !== null && typeof encIn[side] === "object" && !Array.isArray(encIn[side])) {
        enc[side] = expandRoom(encIn[side], norms, type);
      }
    }
    // beimen / nanmen 是「门本体」声明（垂花门等）：只带 role，不带数值。
    for (const k of ["beimen", "nanmen"]) {
      if (encIn[k] !== null && typeof encIn[k] === "object" && !Array.isArray(encIn[k])) {
        enc[k] = { role: encIn[k].role };
      }
    }
    const c = {
      id: `cy${seq}`, name: courtName(seq, jin), sequence: seq,
      enclosure: enc, center: { role: "tingyuan" },
    };
    if (spec.perimeter) c.perimeter = true;
    if (spec.peripheral) {
      c.peripheral = spec.peripheral
        .filter((p) => p !== null && typeof p === "object" && !Array.isArray(p))
        .map((p) => ({ role: p.role }));
    }
    courtyards.push(c);
  });

  return finish(jin, courtyards, rules, dict, opts.omit ?? null);
}

// ---------------- CLI ----------------

function parseArgs(argv) {
  const out = { knowledge: path.join(HERE, "knowledge"), skeleton: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--knowledge") out.knowledge = argv[++i];
    else if (argv[i] === "--skeleton") out.skeleton = argv[++i];
    else if (argv[i] === "--omit") out.omit = argv[++i].split(",").filter(Boolean);
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  let raw;
  if (args.skeleton) {
    raw = fs.readFileSync(args.skeleton, "utf-8");
  } else {
    raw = fs.readFileSync(0, "utf-8"); // stdin
  }
  const plan = JSON.parse(raw);
  const inst = assembleInstance(plan, args.knowledge, { omit: args.omit ?? null });
  process.stdout.write(JSON.stringify(inst, null, 2));
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) main();
