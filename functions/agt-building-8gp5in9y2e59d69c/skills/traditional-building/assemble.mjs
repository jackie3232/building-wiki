#!/usr/bin/env node
/**
 * BUILDING.WIKI · 智能化层 · 装配器（Agent 原生 / Node）
 * ============================================================
 * 职责：LLM 骨架（纯 role + 业务量） -> 自包含实例图谱。
 *
 * 这是智能化层 ① 装配的**唯一实现**（Agent 原生 / Node）。曾有一份同契约的
 * Python 版住在引擎侧作参照，已随 2026-09-27 位置梳理删除——装配逻辑现只此一处。
 *
 * 分层依据（架构设计总览 §13.4 / geometry.py 顶部分层注释）：
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
 *   node assemble.mjs --style <style> --skeleton <file.json>   # 输出图谱 JSON 到 stdout
 *   或： cat skeleton.json | node assemble.mjs --style <style>
 *   默认 --style=siheyuan，--packs 取脚本同目录下的 ./packs（约定优于配置：packs/<style>/）。
 *
 * 出口自校验：跑 validateInstanceGraph（实例图谱合规硬闸的唯一实现，在装配出口做一次）。
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));

// 骨架里允许携带的建筑声明字段：
// 声明性的（门 / 穿堂）+ 业务量（面阔…）。业务量的值域由 rules.paramRanges 约束（见 validatePlan）。
const ROOM_DECL_KEYS = ["gate", "chuantang", "miankuo"];

const CN_NUM = { 1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十" };

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf-8"));
}

// ---------------- 知识中心 ----------------

/** 读知识包三件套（rules / type / dict）。
 *  style = 包目录名：packs/<style>/{<style>.rules, <style>.type.json, dict.json}
 *  约定优于配置——新增风格只需在 packs/ 下加一个目录，引擎零改动。
 *  未知风格须报「图谱缺陷」并列出可用包，不能把裸 ENOENT 栈丢出去
 *  （那种报错会把人/LLM 引向「文件路径写错了」，而不是「这个风格还没建包」）。 */
function loadKnowledge(style, baseDir = path.join(HERE, "packs")) {
  const dir = path.join(baseDir, style);
  if (!fs.existsSync(dir)) {
    let avail = [];
    try {
      avail = fs.readdirSync(baseDir, { withFileTypes: true })
        .filter((d) => d.isDirectory()).map((d) => d.name);
    } catch { /* 包根都读不到时只报 style 未知 */ }
    throw new Error(`图谱缺陷：未知风格「${style}」—— packs/ 下无此知识包`
                    + (avail.length ? `（可用：${avail.join(" / ")}）` : "")
                    + "；风格事实全在 packs 里，不要臆造 style");
  }
  return {
    rules: loadJson(path.join(dir, `${style}.rules`)),
    type: loadJson(path.join(dir, `${style}.type.json`)),
    dict: loadJson(path.join(dir, "dict.json")),
  };
}

// ---------------- 附属知识快照 ----------------
//
// 设计纪律（架构总纲 §4「衔接三要素」/ §8 公式 instance = ontology + parameters）：
//   实例图谱**自包含** —— 装配出口把本风格知识中心**三件套整份**以快照嵌入
//   （appliedRules / appliedType / appliedDict）；自动化端（④⑤ / 硬闸）只引用实例图谱
//   自带的快照，**绝不回读盘包**（自动化端容器亦不 COPY packs）。
//
// 历史包袱（2026-09-28 清掉）：此处曾是「按需裁剪」——代码里硬编两张「要保留的键名清单」
// （NORMS_ALWAYS 原型键 + 四个角色名前缀），既违「引擎零风格硬编」（总纲 7 判据 1），
// 又让「快照范围」变成引擎的隐性知识；更糟的是裁剪会**裁掉合法词**，使下游报错里列出的
// 合法集不完整（DICT_FULL_KEEP 那条补丁即为此）。改为整份快照后：引擎零裁剪、零键名清单，
// 上述整类问题结构性消失。

// ---------------- 装配 ----------------

/** 一栋建筑的声明：role + 尺度 + 该栋自身属性（等级/材质/高度/台明）。
 *  等级/材质取自命名字典「空间角色」条目（单一命名权威，见总纲8(a)）；type 只 ref 不重声明。
 *  尺度缺省值与「门开在哪个开间」取自 rules.norms —— 原先这里是字面量 5 / 3 / "mingjian"。 */
function room(role, norms, dictDoc) {
  const n = norms?.[role] ?? {};
  const d = dictDoc?.["空间角色"]?.[role] ?? {};
  const df = norms?.room ?? {};
  const doorAt = norms?.door?.at;
  if (doorAt === undefined) {
    throw new Error("图谱缺陷：规则库缺少 norms.door.at（房门开在哪个开间，开间词表的 key）");
  }
  const pick = (key, fallbackKey) => {
    if (n[key] !== undefined) return n[key];
    if (df[fallbackKey] === undefined) {
      throw new Error(`图谱缺陷：role=${role} 未声明 ${key}，且规则库缺少 norms.room.${fallbackKey}（回落基准）`);
    }
    return df[fallbackKey];
  };
  const r = {
    role,
    miankuo: pick("miankuo", "miankuoDefault"),
    jinshen: pick("jinshen", "jinshenDefault"),
    // 朝院门洞：各房门窗均向院内开辟，门在明间(正中开间)。
    // 开向不进图谱——由房屋所在侧推得，属几何事实；写进图谱就变成引擎级动作了。
    door: { at: doorAt },
  };
  for (const k of ["height", "taiming"]) if (n[k] !== undefined && n[k] !== null) r[k] = n[k];
  for (const k of ["level", "material"]) if (d[k] !== undefined && d[k] !== null) r[k] = d[k];
  return r;
}

/** 骨架里的建筑声明 -> 完整建筑：role 查表补全尺度/等级/材质，声明字段原样合上。 */
function expandRoom(spec, norms, dictDoc) {
  if (spec === null || typeof spec !== "object" || Array.isArray(spec) || !spec.role) {
    throw new Error(`图谱缺陷：骨架中的建筑声明缺 role：${JSON.stringify(spec)}`);
  }
  const r = room(spec.role, norms, dictDoc);
  for (const k of ROOM_DECL_KEYS) if (k in spec) r[k] = spec[k];
  return r;
}

// ---------------- 第一级合法性闸（词表 + 值域 + 结构） ----------------
// 理解层产物准入（装配器侧）：
// 这是**理解层产物**的准入检查，不是几何校验。任何一项不过即抛错——不静默放行。
// 值域取自知识中心 rules.paramRanges：真值域是知识中心的一个旋钮，改域不改码。

const SIDES = ["bei", "nan", "dong", "xi"];

/** 合法 role 集 = 命名字典「空间角色」（单一命名权威；type 只 ref 不声明，见总纲8(a)）。 */
function legalRoles(dictDoc) {
  return new Set(Object.keys(dictDoc?.["空间角色"] ?? {}));
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

/** 第一级合法性闸：plan 必须词表内、值域内、结构完整。返回 plan（便于串联）。
 *  只消费 rules（值域）与 dict（词表）——type 不参与本闸（type 的 ref 守卫在 validateInstanceGraph）。 */
function validatePlan(plan, { rules, dict }) {
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
    throw new Error("图谱缺陷：规则库缺少 paramRanges.jin.range（值域未声明）");
  }
  const [lo, hi] = rng;
  if (jin < lo || jin > hi) {
    throw new Error(`图谱缺陷：jin=${jin} 超出知识中心声明值域 ${lo}-${hi}`);
  }
  if (specs.length !== jin) {
    throw new Error(`图谱缺陷：jin=${jin} 与 courtyards 数量 ${specs.length} 不符`);
  }
  const roles = legalRoles(dict);
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
    throw new Error("图谱缺陷：规则库缺少 sequence.naming.rules / .fallback");
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
    if (n < (fallback.ordinalFrom ?? 2)) {
      throw new Error(
        `图谱缺陷：第 ${k} 进（共 ${jin} 进）在 sequence.naming 中无规则命中，` +
        `且不满足 fallback 序数（序数算出为 ${n}）`);
    }
    return `${lbl(fallback.name)}·${CN_NUM[n] !== undefined ? CN_NUM[n] : String(n)}`;
  };
}

const roleOf = (obj, dflt = null) =>
  obj !== null && typeof obj === "object" && !Array.isArray(obj) ? (obj.role ?? dflt) : dflt;

/**
 * 门体 role：节点不存在返回 null；节点在、role 缺 → 报图谱缺陷。
 * 门的种类（垂花门 / 宅门 / …）事实源是知识包，产出侧只回读，绝不写死常量；
 * 缺 role 时若静默回落，会变成「墙上有门却不开口」这种看不出来的错误。
 */
function gateRoleOf(node, ctx) {
  if (node === null || node === undefined || node === false) return null;
  const r = roleOf(node, null);
  if (!r) throw new Error(`图谱缺陷：${ctx} 声明了门体却缺 role —— 门的种类须由知识包声明`);
  return r;
}

/** 规则库里 `when` 条件的求值（如 "jin>=4" / "jin==2" / null=恒真）。 */
function jinCondOk(cond, jin) {
  if (!cond) return true;
  const m = /^\s*jin\s*(>=|<=|==|>|<)\s*(\d+)\s*$/.exec(String(cond));
  if (!m) throw new Error(`图谱缺陷：rules 中无法求值的 when 条件「${cond}」`);
  const op = m[1], n = parseInt(m[2], 10);
  return { ">=": jin >= n, "<=": jin <= n, "==": jin === n, ">": jin > n, "<": jin < n }[op];
}

/**
 * 收尾：usage 标注 -> 院角色判定 -> ring 声明 -> 打包附属知识。纯机械，零推理。
 *
 * 「零风格硬编」在本函数的落点：凡「哪一进算什么院 / 这侧墙算什么墙种」这类**风格事实**，
 * 一律由知识包声明（dict 的角色词条 + rules），代码只按声明求值——原先这里硬编着
 * `"zhengfang"` / `"guoting"` / `"kaziqiang"` / `"houyanqiang"` / `"weiqiang"` 五串角色名。
 */
function finish(jin, courtyards, rulesDoc, typeDoc, dictDoc, style) {
  // 原此处有 omit 裁剪（--omit：抹掉指定侧建筑，用于验证「去掉建筑→外墙自动补上」）。
  // 2026-09-27 删除：它要验的性质已由 ④ 的 _geo_wall_ring + _resolve_boundary 结构性保证
  // （先画整圈墙、再按建筑真实覆盖做区间相减），直接构造 instance 即可验证；
  // 而该开关本身与装配出口硬闸（validateInstanceGraph 按同一份 occupancy）方向相反，
  // 任何可用取值都会被硬闸拒掉 —— 留着一个永远报错的开关只会误导。
  // 若将来要支持「某侧可选」的合法变体，应由规则库声明 + 骨架表达，而非加回 CLI 开关。

  // 用途(usage)：图谱声明「某角色在某情形下作何用途」——如四进院第二进院正位房作过厅。
  // 落点由规则库的**机器槽位** `slot:{court,side}` 给出；原先代码里写的是中文槽位
  // "erjinyuan_zhengwei"，等于把「第几进 + 哪一侧」硬编进引擎（总纲 7 判据 1）。
  for (const u of rulesDoc?.usage ?? []) {
    const slot = u.slot;
    if (!u.role || !u.usage || !slot || !jinCondOk(u.when, jin)) continue;
    const idx = Number(slot.court) - 1;
    if (!Number.isInteger(idx) || idx < 0 || idx >= courtyards.length) continue;
    const nm = (courtyards[idx].enclosure ?? {})[slot.side];
    if (nm && roleOf(nm, null) === u.role) nm.usage = u.usage;
  }

  // 院角色（外院/内院/厅房院/后罩院/庭院）：读 rules.sequence.courtRole —— 院角色的唯一事实源。
  // 做法：先找「锚点进」（主位房所在的那一进），锚点之前/之后/自身各取声明里的院角色。
  // 原先这里硬编 "zhengfang"/"guoting"/"tingyuan"/"neiyuan"/"waiyuan"/"houzhaoyuan"/"tingfangyuan"。
  const crRule = rulesDoc?.sequence?.courtRole;
  const anchor = crRule?.anchor;
  const roleMap = crRule?.roles;
  if (!anchor || !anchor.side || !anchor.role || !roleMap
      || !roleMap.anchor || !roleMap.before || !roleMap.after || !roleMap.single) {
    throw new Error("图谱缺陷：规则库缺少 sequence.courtRole（anchor.side/role + roles.*）"
                    + "——院角色推导无依据");
  }
  const usageCourtRole = crRule.usageCourtRole ?? {};
  let anchorIdx = null;
  for (let i = 0; i < courtyards.length; i++) {
    const main = (courtyards[i].enclosure ?? {})[anchor.side];
    if (roleOf(main, null) !== anchor.role) continue;
    const u = main.usage;
    // 主位房带 usage 且在 usageCourtRole 中命中者不算主院（过厅是前堂，不是后寝）
    if (u !== undefined && Object.prototype.hasOwnProperty.call(usageCourtRole, u)) continue;
    anchorIdx = i;
    break;
  }
  for (let i = 0; i < courtyards.length; i++) {
    const c = courtyards[i];
    if (anchorIdx === null || i === anchorIdx) {
      c.role = courtyards.length === 1 ? roleMap.single : roleMap.anchor;
    } else if (i < anchorIdx) {
      const u = ((c.enclosure ?? {})[anchor.side] ?? {}).usage;
      c.role = usageCourtRole[u] || roleMap.before;
    } else {
      c.role = roleMap.after;
    }
  }

  // 墙种指派：读 rules.wall.assign —— 「这侧墙算什么墙种」的唯一事实源。
  // 原先这里硬编 "kaziqiang" / "houyanqiang" / "weiqiang" 三串墙种 key。
  const wa = rulesDoc?.wall?.assign;
  if (!wa || !wa.withBuilding || !wa.standalone || !wa.withGate) {
    throw new Error("图谱缺陷：规则库缺少 wall.assign（withBuilding/standalone/withGate）"
                    + "——院墙墙种指派无依据");
  }
  // 有独立门本体 → 门所在的那道分隔墙；否则有建筑贴边 → 建筑后檐墙兼作院墙；再否则 → 独立院墙。
  const kindFor = (provider, hasStandaloneGate) =>
    hasStandaloneGate ? wa.withGate : (provider ? wa.withBuilding : wa.standalone);

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

    // 北界：若本进北侧四至是**独立门本体**（beimen 槽位），则该界无建筑 provider，门自己成墙。
    const nHasGate = !!enc.beimen;
    const nProv = nHasGate ? null : nr;
    const nKind = kindFor(nProv, nHasGate);
    const nGate = nHasGate
      ? gateRoleOf(enc.beimen, `courtyards[${i}].enclosure.beimen`)
      : gateRoleOf(enc.bei?.gate, `courtyards[${i}].enclosure.bei.gate`);

    let sProv, sGate, sThru;
    if (i === 0) {
      sProv = sr;
      sGate = gateRoleOf(enc.nan?.gate, `courtyards[${i}].enclosure.nan.gate`);
      sThru = null;
    } else {
      sProv = prevNr;
      if (prevEnc.beimen) {
        sGate = gateRoleOf(prevEnc.beimen, `courtyards[${i - 1}].enclosure.beimen`);
        sThru = null;
      } else if (prevEnc.bei?.chuantang) {
        // 穿堂不是门：它是上一进北房「明间前后贯通」的做法，随正房归属上一进院。
        // 注：`chuantang` 在此是**骨架声明字段名**（ROOM_DECL_KEYS，schema 的一部分），
        // 不是从词表查出来的角色名——该字段的消费者是 ④ 的 _geo_house。
        sGate = null;
        sThru = { via: "chuantang", of: prevNr, courtyard: courtyards[i - 1].name };
      } else {
        sGate = null; sThru = null;
      }
    }

    c.ring = {
      bei: { provider: nProv, kind: nKind, gate: nGate },
      nan: { provider: sProv, kind: kindFor(sProv, false), gate: sGate, thru: sThru },
      dong: { provider: er, kind: kindFor(er, false) },
      xi: { provider: wr, kind: kindFor(wr, false) },
    };
  }

  return wrap(jin, courtyards, rulesDoc, typeDoc, dictDoc, style);
}

/** instance = data（实例参数）+ 知识中心三件套整份快照（本体）。
 *  §8 公式：instance graph = ontology( dict + type graph + rules ) + parameters。
 *  style 即知识包标识（packs/<style>/），写进 instance 供 ④⑤ / 校验器溯源。 */
function wrap(jin, courtyards, rulesDoc, typeDoc, dictDoc, style,
              generatedBy = "assemble.mjs (skill traditional-building)") {
  const data = { type: style, jin, courtyards };
  const inst = {
    style,
    meta: {
      type: style,
      desc: `${style} ${jin}进实例（由类型图谱+规则库合成，工程文件·自包含）`,
      generatedBy,
      zeroCoord: true,
    },
    data,
    // 本体三件套**整份**：dict(词汇层) / type(结构层) / rules(约束层)。引擎不裁剪、不列键名。
    appliedRules: rulesDoc ?? {},
    appliedType: typeDoc ?? {},
  };
  if (dictDoc !== null && dictDoc !== undefined) {
    inst.appliedDict = dictDoc;
  }
  return inst;
}

// ---------------- 第二级硬闸：实例图谱 regime 校验（occupancy + position） ----------------
// 实例图谱合规校验的**唯一实现**（事实源：知识包的 occupancy.rules / position）。
// 性质：确定性、非智能化；装配出口 fail-fast，使 Agent 在调 generate_building(55s MCP) 前
// 拦住违规骨架。这是「理解层产物准入」(validatePlan) 之上的「几何前置准入」——后者只查
// 词表/值域/结构，本闸补查「四至构成与门位」这类只有 occupancy/position 才定义的规制。

/** 取 occupancy.rules；缺失即报图谱缺陷。 */
function occupancyRules(rulesDoc) {
  const occ = rulesDoc?.occupancy?.rules ?? null;
  if (!Array.isArray(occ) || occ.length === 0) {
    throw new Error("图谱缺陷：规则库缺少 occupancy.rules（院落四至默认构成）");
  }
  return occ;
}

/** 第 k 进的四至规则：按序求值、首个命中者胜出。 */
function occupancyOf(k, jin, occRules) {
  for (const r of occRules) {
    const at = r.at;
    if (at === "middle") { if (!(1 < k && k < jin)) continue; }
    else if (at === "last") { if (k !== jin) continue; }
    else if (at !== k) continue;
    if ("jinEq" in r && jin !== r.jinEq) continue;
    if ("jinGte" in r && jin < r.jinGte) continue;
    if ("jinLte" in r && jin > r.jinLte) continue;
    return r;
  }
  throw new Error(`图谱缺陷：第 ${k} 进（共 ${jin} 进）在 rules.occupancy 无规则命中`);
}

// ---------------- position 段：构件位置规制（数据驱动，代码零硬编角色名） ----------------
// 事实源唯一：rules.position。代码只做「按 mount 取槽位 + 按 court/when 判第几进」，
// 不出现任何具体角色名（垂花门/宅门/后门的约束一律写在规则库里）。
// 「mount」声明该角色可挂的槽位（"beimen" / "nan.gate" / "bei.gate" / …），
// 「court」声明可出现的进（1 / "middle" / "last"），「when」为该段的既有可求值条件。

/** position 段中带机器槽位(mount)的条目 —— 只有这些参与门位准入校验。 */
function positionMounts(rulesDoc) {
  const pos = rulesDoc?.position;
  if (!Array.isArray(pos)) {
    throw new Error("图谱缺陷：规则库缺少 position 段（构件位置约束）");
  }
  return pos.filter((p) => p !== null && typeof p === "object" && typeof p.mount === "string");
}

/** 取 mount 指向的槽位（"nan.gate" -> enclosure.nan.gate）。 */
function slotOf(enclosure, mount) {
  let cur = enclosure;
  for (const k of String(mount).split(".")) {
    if (cur === null || typeof cur !== "object" || Array.isArray(cur)) return null;
    cur = cur[k];
  }
  return cur;
}

const roleInSlot = (enclosure, mount) => roleOf(slotOf(enclosure, mount), null);

/** 第 seq 进（共 jin 进）是否满足 position 条目的 court / jin* / when 条件。 */
function courtMatchOk(seq, jin, entry) {
  const court = entry.court;
  if (court !== undefined && court !== null) {
    if (court === "last") { if (seq !== jin) return false; }
    else if (court === "middle") { if (!(1 < seq && seq < jin)) return false; }
    else if (seq !== Number(court)) return false;
  }
  if ("jinEq" in entry && jin !== entry.jinEq) return false;
  if ("jinGte" in entry && jin < entry.jinGte) return false;
  if ("jinLte" in entry && jin > entry.jinLte) return false;
  return jinCondOk(entry.when, jin);
}

/** 某 role 是否被 position 声明可挂在该侧——用于 occupancy「不应嵌门」的豁免判定。 */
function mountAllows(positions, role, side) {
  return positions.some((p) => p.role === role && p.mount === `${side}.gate`);
}

/** 合法院落角色集 = 命名字典「院落」段词表（唯一事实源；代码不得硬编）。 */
function legalCourtRoles(dictDoc) {
  const set = new Set(Object.keys(dictDoc?.["院落"] ?? {}));
  if (!set.size) throw new Error("图谱缺陷：命名字典缺少「院落」段（院落角色词表）");
  return set;
}

/** 域②(a) type.ref 守卫：类型图谱内所有指向 dict key 的引用必须命中命名字典（单一命名权威，见总纲6域②(a)/总纲8(a)）。
 *  收集规则：字段名恰为 `ref`，或以 `Ref` 结尾（如 wallRef / providerRef / attachToRef）；
 *  **跳过 meta 段**——其中的 dictRef / rulesRef 是文件引用而非 dict key，不参与本守卫。
 *  缺失即报「图谱缺陷」——type 不得引入 dict 未登记的词。 */
function assertTypeRefsHitDict(typeDoc, dictDoc) {
  const dictKeys = new Set();
  for (const [cat, entries] of Object.entries(dictDoc ?? {})) {
    if (cat === "meta" || entries === null || typeof entries !== "object" || Array.isArray(entries)) continue;
    for (const k of Object.keys(entries)) dictKeys.add(k);
  }
  const refs = [];
  const walk = (o, inMeta) => {
    if (Array.isArray(o)) { for (const v of o) walk(v, inMeta); }
    else if (o !== null && typeof o === "object") {
      for (const [k, v] of Object.entries(o)) {
        const isMeta = inMeta || k === "meta";
        if (!isMeta && typeof v === "string" && (k === "ref" || /Ref$/.test(k))) refs.push(v);
        walk(v, isMeta);
      }
    }
  };
  walk(typeDoc, false);
  const bad = [...new Set(refs)].filter((r) => !dictKeys.has(r));
  if (bad.length) {
    throw new Error(`图谱缺陷：类型图谱 ref/*Ref 未命中命名字典：${JSON.stringify(bad)}（角色名/属性须全走 dict key，单一命名权威）`);
  }
}

/**
 * 实例图谱硬闸：装配出口强制调用。返回 true 或抛「图谱缺陷」。
 * @param {object} instance 自包含实例图谱（assemble 产物）
 * @param {object} rulesDoc 完整规则库（occupancy/position/paramRanges）
 * @param {object} typeDoc 类型图谱
 * @param {object} dictDoc 命名字典
 */
export function validateInstanceGraph(instance, rulesDoc, typeDoc, dictDoc) {
  if (instance === null || typeof instance !== "object" || Array.isArray(instance)) {
    throw new Error("图谱缺陷：校验器收到非对象 instance");
  }
  const data = instance.data ?? instance;
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("图谱缺陷：instance.data 须为对象");
  }
  const courtyards = data.courtyards;
  if (!Array.isArray(courtyards) || courtyards.length === 0) {
    throw new Error("图谱缺陷：instance.data.courtyards 缺失或为空");
  }
  // 域②(a) type.ref 守卫：type 内所有 ref 须命中 dict（单一命名权威）
  assertTypeRefsHitDict(typeDoc, dictDoc);
  const jin = data.jin;
  if (!Number.isInteger(jin) || jin < 1) {
    throw new Error(`图谱缺陷：jin 须为正整数，实际 ${JSON.stringify(jin)}`);
  }
  if (courtyards.length !== jin) {
    throw new Error(`图谱缺陷：courtyards 数量 ${courtyards.length} 与 jin=${jin} 不符`);
  }

  // sequence 须为 1..jin 且唯一
  const seqs = courtyards.map((c) => c.sequence);
  const expect = [...Array(jin)].map((_, i) => i + 1);
  if (JSON.stringify([...seqs].sort((a, b) => a - b)) !== JSON.stringify(expect)) {
    throw new Error(`图谱缺陷：courtyards.sequence 须为 1..${jin} 且唯一，实际 ${JSON.stringify(seqs)}`);
  }

  // 词表（role 白名单）= dict「空间角色」单一权威
  const roles = legalRoles(dictDoc);
  // 构件位置规制 + 合法院落角色（均取自知识包，代码零硬编）
  const positions = positionMounts(rulesDoc);
  const courtRoles = legalCourtRoles(dictDoc);
  const used = new Set();
  for (const c of courtyards) {
    const enc = c.enclosure ?? {};
    for (const key of ["bei", "nan", "dong", "xi", "beimen", "nanmen"]) {
      const r = enc[key];
      if (r !== null && typeof r === "object" && !Array.isArray(r) && r.role) used.add(r.role);
    }
    for (const p of c.peripheral ?? []) {
      if (p !== null && typeof p === "object" && !Array.isArray(p) && p.role) used.add(p.role);
    }
  }
  const bad = [...used].filter((r) => !roles.has(r));
  if (bad.length) {
    throw new Error(`图谱缺陷：实例图谱含未登记角色 ${JSON.stringify(bad)}（不在 dict.空间角色 词表内）`);
  }

  // 值域（paramRanges）
  const pr = rulesDoc?.paramRanges ?? {};
  const jr = pr?.jin?.range;
  if (Array.isArray(jr) && jr.length === 2 && (jin < jr[0] || jin > jr[1])) {
    throw new Error(`图谱缺陷：jin=${jin} 超出 paramRanges.jin 值域 ${JSON.stringify(jr)}`);
  }
  const mkCfg = pr?.miankuo ?? {};
  const mkRng = mkCfg.range ?? [1, 7];
  const mkLo = mkRng[0], mkHi = mkRng[1];
  const mkStep = Number.isInteger(mkCfg.step) && mkCfg.step > 0 ? mkCfg.step : 2;
  for (const c of courtyards) {
    for (const side of ["bei", "nan", "dong", "xi"]) {
      const r = c.enclosure?.[side];
      const mk = r?.miankuo;
      if (Number.isInteger(mk)) {
        if (mk < mkLo || mk > mkHi) {
          throw new Error(`图谱缺陷：第 ${c.sequence} 进 ${side} 面阔 miankuo=${mk} 超出 paramRanges.miankuo 值域 [${mkLo},${mkHi}]`);
        }
        if (mkStep && (mk - mkLo) % mkStep !== 0) {
          const seq = [...Array(Math.floor((mkHi - mkLo) / mkStep) + 1)].map((_, i) => mkLo + i * mkStep);
          throw new Error(`图谱缺陷：第 ${c.sequence} 进 ${side} 面阔 miankuo=${mk} 须为步长 ${mkStep} 的序列 ${JSON.stringify(seq)}`);
        }
      }
    }
  }

  // occupancy regime（四至构成）
  const occRules = occupancyRules(rulesDoc);
  const seenNames = new Set();
  for (const c of courtyards) {
    const seq = c.sequence;
    const enc = c.enclosure ?? {};
    const rule = occupancyOf(seq, jin, occRules);
    const rid = rule.id ?? "?";

    const expSides = {};
    for (const side of ["bei", "nan", "dong", "xi"]) {
      const spec = rule.sides?.[side];
      if (spec) expSides[side] = spec;
    }
    for (const [side, spec] of Object.entries(expSides)) {
      const actual = enc[side];
      if (actual === null || typeof actual !== "object" || Array.isArray(actual) || roleOf(actual, null) !== spec.role) {
        throw new Error(`图谱缺陷：第 ${seq} 进(共 ${jin} 进) 四至「${side}」应为 ${spec.role}，实际为 ${roleOf(actual, null)}（occupancy.${rid} 约束）`);
      }
      const expGate = spec.gate?.role ?? null;
      const ag = actual.gate;
      const actGate = ag !== null && typeof ag === "object" && !Array.isArray(ag) ? ag.role : null;
      if (expGate !== null && expGate !== actGate) {
        throw new Error(`图谱缺陷：第 ${seq} 进 四至「${side}」所嵌门应为 ${expGate}，实际为 ${actGate}（occupancy.${rid} 约束）`);
      }
      if (expGate === null && actGate !== null && !mountAllows(positions, actGate, side)) {
        throw new Error(`图谱缺陷：第 ${seq} 进 四至「${side}」按 occupancy.${rid} 不应嵌门，实际嵌了 ${actGate}（且 position 段未声明该侧可挂此门）`);
      }
    }
    for (const side of ["bei", "nan", "dong", "xi"]) {
      if (!(side in expSides) && enc[side] !== null && enc[side] !== undefined) {
        throw new Error(`图谱缺陷：第 ${seq} 进 四至「${side}」按 occupancy.${rid} 不应有建筑，实际存在 ${roleOf(enc[side], null)}`);
      }
    }
    const expBeimen = rule.beimen?.role ?? null;
    if (roleOf(enc.beimen, null) !== expBeimen) {
      throw new Error(`图谱缺陷：第 ${seq} 进 beimen 应为 ${expBeimen}，实际为 ${roleOf(enc.beimen, null)}（occupancy.${rid} 约束）`);
    }
    const expPer = new Set((rule.peripheral ?? []).map((p) => p.role).filter(Boolean));
    const actPer = new Set((c.peripheral ?? []).map((p) => p.role).filter(Boolean));
    if (JSON.stringify([...expPer].sort()) !== JSON.stringify([...actPer].sort())) {
      throw new Error(`图谱缺陷：第 ${seq} 进 peripheral 应为 ${JSON.stringify([...expPer].sort())}，实际为 ${JSON.stringify([...actPer].sort())}（occupancy.${rid} 约束）`);
    }
    if (Boolean(rule.perimeter) !== Boolean(c.perimeter)) {
      throw new Error(`图谱缺陷：第 ${seq} 进 perimeter 应为 ${Boolean(rule.perimeter)}，实际为 ${Boolean(c.perimeter)}（occupancy.${rid} 约束）`);
    }

    // 院落命名（naming）轻量校验
    const name = c.name;
    if (typeof name !== "string" || !name.trim()) {
      throw new Error(`图谱缺陷：第 ${seq} 进 院名为空（sequence.naming 推导失败）`);
    }
    if (seenNames.has(name)) {
      throw new Error(`图谱缺陷：院名「${name}」重复（sequence.naming 须唯一）`);
    }
    seenNames.add(name);
    const cr = c.role;
    if (cr !== null && cr !== undefined && !courtRoles.has(cr)) {
      throw new Error(`图谱缺陷：院落角色 ${JSON.stringify(cr)} 非法（须为 dict.json「院落」段词表：${[...courtRoles].join("/")}）`);
    }
  }

  // position 校验（构件位置规制）：逐条读规则库 position 段求值，代码不硬编任何角色名。
  for (const p of positions) {
    for (const c of courtyards) {
      if (roleInSlot(c.enclosure ?? {}, p.mount) !== p.role) continue;
      if (!courtMatchOk(c.sequence, jin, p)) {
        const cond = [`mount=${p.mount}`];
        if (p.court !== undefined) cond.push(`court=${p.court}`);
        if (p.when) cond.push(`when=${p.when}`);
        throw new Error(
          `图谱缺陷：${p.role} 出现在第 ${c.sequence} 进（共 ${jin} 进），违反规则库 position 段约束`
          + `（${cond.join(" / ")}）${p.desc ? " —— " + p.desc : ""}`);
      }
    }
  }

  // appliedRules.norms 轻量完整性
  const norms = instance.appliedRules?.norms ?? {};
  if (!("modus" in norms)) {
    throw new Error("图谱缺陷：instance.appliedRules.norms.modus 缺失（④ 布局第一步即消费）");
  }

  return true;
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
 * - 收尾与 CLI 直跑共用 finish，故两条入口出的形状必然一致。
 */
export function assembleInstance(plan, packsRoot, opts = {}) {
  // 风格**必填**：来自 --style 或骨架的 style。代码里不设任何默认风格——默认风格字面量
  // 就是「具体建筑类型硬编」（总纲 7 判据 1）；缺了即报错，由理解层补上，不猜。
  const style = opts.style || plan.style;
  if (typeof style !== "string" || !style) {
    throw new Error("图谱缺陷：骨架缺 style（风格标识），且未传 --style —— "
                    + "风格必须显式给出，装配器不设默认（默认值会让「缺字段」被静默吞掉）");
  }
  const { rules, type, dict } = loadKnowledge(style, packsRoot);
  const norms = rules.norms ?? {};
  const courtName = courtNamer(rules, dict);

  // 第一级合法性闸：词表 + 值域 + 结构。不过即抛错（该骨架作废，须回理解层重出）。
  validatePlan(plan, { rules, dict });
  const specs = plan.courtyards;
  const jin = Number(plan.jin);

  // 结构层事实（type 图谱）：院落中心角色 / 院与墙环的关系。两个 key 原先硬编在代码里
  // （center.role="tingyuan"、enc.relation="weihe"），而 type 图谱 `courtyard.center.ref` /
  // `courtyard.ring.ref` 已经声明同一事实——读 type 而不另立一份，避免「同一事实两处表达」。
  const cyType = type?.courtyard;
  const centerRole = cyType?.center?.ref;
  const ringRelation = cyType?.ring?.ref;
  if (!centerRole || !ringRelation) {
    throw new Error("图谱缺陷：类型图谱缺少 courtyard.center.ref / courtyard.ring.ref"
                    + "（院落中心角色与墙环关系，结构层事实）");
  }

  const courtyards = [];
  specs.forEach((spec, i) => {
    if (spec === null || typeof spec !== "object" || Array.isArray(spec)) {
      throw new Error(`图谱缺陷：courtyards[${i}] 不是对象`);
    }
    const seq = Number(spec.sequence || (i + 1));
    const encIn = spec.enclosure ?? {};
    const enc = { relation: encIn.relation || ringRelation };
    for (const side of ["bei", "nan", "dong", "xi"]) {
      if (encIn[side] !== null && typeof encIn[side] === "object" && !Array.isArray(encIn[side])) {
        enc[side] = expandRoom(encIn[side], norms, dict);
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
      enclosure: enc, center: { role: centerRole },
    };
    if (spec.perimeter) c.perimeter = true;
    if (spec.peripheral) {
      c.peripheral = spec.peripheral
        .filter((p) => p !== null && typeof p === "object" && !Array.isArray(p))
        .map((p) => ({ role: p.role }));
    }
    courtyards.push(c);
  });

  const inst = finish(jin, courtyards, rules, type, dict, style);
  // 装配出口硬闸：实例图谱 regime 校验（occupancy + position）。不过即抛错，
  // 使 Agent 在调 generate_building（数十秒的 MCP 往返）前 fail-fast。
  // 这是实例图谱合规校验的**唯一实现**（2026-09-27 定）：服务端不再重复校验，
  // 那一侧的守卫只剩 ④ 自带的形状闸 _graph_data（入参非自包含图谱即报错）。
  validateInstanceGraph(inst, rules, type, dict);
  return inst;
}

// ---------------- CLI ----------------

function parseArgs(argv) {
  const out = { packs: path.join(HERE, "packs"), skeleton: null, style: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--packs") out.packs = argv[++i];
    else if (argv[i] === "--style") out.style = argv[++i];
    else if (argv[i] === "--skeleton") out.skeleton = argv[++i];
    // 未知参数一律报错，不静默忽略——静默忽略会让人以为某个开关生效了（--omit 就是这么被误用的）。
    else throw new Error(`图谱缺陷：assemble.mjs 不认识参数「${argv[i]}」（支持 --packs / --style / --skeleton）`);
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
  const inst = assembleInstance(plan, args.packs, { style: args.style });
  process.stdout.write(JSON.stringify(inst, null, 2));
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) main();
