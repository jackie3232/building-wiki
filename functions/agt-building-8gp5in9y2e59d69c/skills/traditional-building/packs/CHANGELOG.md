# 知识包变更存档 · CHANGELOG

> **定位**：知识包（dict / type graph / rules 三件套）本体与其消费代码的**长期变更存档**。
> **维护约定**：每完成一批知识包相关改动，在文末追加一条版本条目；**只追加、不追改历史条目**（历史条目若需修订，另起"勘误"小节）。
> **落点说明**：本存档属知识包资产，位于 `packs/`（知识包目录）根，与各风格包同级；架构文档（`docs/架构总纲.md`、`docs/知识包三件套定义.md`）不在此处。

---

## 版本口径

本存档记录**三类版本锚点**，缺一不可：

| 锚点 | 载体 | 说明 |
|---|---|---|
| **知识包版本** | 本文件条目号 `packs vX.Y.Z` | 自本存档建立时**新起**；语义见下。此前无版本号载体，历史不追溯编造。 |
| **代码版本** | git commit + 工作区状态 | 知识包消费代码（`assemble.mjs` 等）所属的 git 锚点。改动未提交时，锚点为「HEAD + 未提交工作区」并附**文件指纹（md5）**。 |
| **线上版本** | CloudBase 部署版本号 | 部署版本号（如 `building-wiki-0xx`）；仅当改动随某版本上线时填写，否则标「未上线」。 |

**知识包语义版本规则**（自本存档起生效）：

- `v0`：种子/占位阶段，包内结构可能整体替换。
- `v0.Y`：**归口/结构级**改动（三件套职责边界变动、字段归一、命名权威调整）。
- `v0.Y.Z`：**内容/数据级**改动（补条目、补属性、改数值），不改结构契约。
- 不因文档改动单独升版本；文档改动随当次改动一并记录。

---

## packs v0.2.0 — 2026-09-28

**主题**：知识包三件套**归口重构**——角色名与属性一律归 dict（单一命名权威），type 只组织不重声明；守卫机器化扩围。

**代码版本**：git `b8dbe8d`（基线）+ **本轮改动未提交**（工作区状态，指纹见下）。
**线上版本**：未上线（`building-wiki-012` 部署于 2026-09-20，**不含**本改动）。

### 0. 前置基线（本轮之前的未提交改动）

本轮建立在上一批**同属未提交**的改动之上，统一记为 `packs v0.1.x` 内容，不再单独开条目：

- `assemble.mjs` 的 `room()`（约 L154–168）改为从 `dictDoc["空间角色"][role]` 读取 `level` / `material`（此前为代码内置表）。
- `packs/siheyuan/dict.json` 的 15 个空间角色补 `level` / `material`（结果：siheyuan 基线含 level/material **37 处**）。

### 1. 变更明细

#### A. type graph 归一（两个风格包）

**文件**：
- `packs/siheyuan/siheyuan.type.json`（147 → 137 行）
- `packs/jiangnan/jiangnan.type.json`（364 → 约 160 行）

**判据**：type 只负责「一词挂到另一词上」的组织关系；角色名/属性名以 dict 为唯一权威 → type 内**所有指向 dict 的字段统一以 `ref` 或 `*Ref` 命名**，从而可被单一守卫机器校验。

| # | 归一动作 | 变更前 | 变更后 | 依据 |
|---|---|---|---|---|
| A1 | 删冗余角色清单 | `roles: { … }`（15 个角色名） | **删除**（角色名归 dict，type 不重声明） | 单一命名权威；分则三问之「某词是什么」→ dict |
| A2 | 字段改名 | `courtyard.refRole` | `courtyard.ref` | 统一 `ref` 前缀，纳入守卫 |
| A3 | 删重复字段 | 各处的 `center.role` / `gate.role` / `peripheral[].role`（值与 `ref` 恒等） | **删除** | 同一事实禁止两处表达 |
| A4 | 字段改名 | `peripheral[].attachTo` | `peripheral[].attachToRef` | 统一 `*Ref` 后缀 |
| A5 | 字段改名 | `ring.sides.*.wall` | `ring.sides.*.wallRef` | 统一 `*Ref` 后缀 |
| A6 | 字段改名 | `ring.sides.*.candidateProvider` | `ring.sides.*.providerRef` | 统一 `*Ref` 后缀 |
| A7 | 删重复字段 | `ring.sides.*.ref`（与 `candidateProvider` 同值） | **删除** | 同一事实禁止两处表达 |

**归一后 type 保留的段**：`meta`（含 `dictRef` / `rulesRef`） / `site` / `courtyard`（`ref` / `center` / `gate` / `peripheral` / `ring`，内部字段全 `*Ref` / `ref`） / `modularParams` / `wall` / `__source_of_truth__`。

#### B. dict 补属性

**B1. `packs/jiangnan/dict.json`（本段改动）**

- **新增条目**：`tingyuan` → `{"label":"庭院","desc":"露天院落，无屋盖","open":true}`
- **补属性 15 条**（`level` / `material` / `modular` / `structs`）：

| 角色 | level | material | modular | structs |
|---|---|---|---|---|
| zhengfang | yideng | qingzhuan | 是 | 7 项 |
| xiangfang | erdeng | qingzhuan | 是 | 与 zhengfang 同 |
| daozuofang | sandeng | qingzhuan | 是 | 与 zhengfang 同 |
| houzhaofang | erdeng | qingzhuan | 无 | — |
| erfang | erdeng | qingzhuan | — | 5 项 |
| chuihuamen | sideng | mugou | — | 3 项 |
| youlang | sideng | mugou | — | 4 项 |
| yingbi | sideng | mohui | — | [qiangti] |
| yuanqiang | sideng | chengzhuan | — | [qiangti] |
| zhaimen | sideng | mugou | 是 | 有 |
| houmen | sideng | mugou | [miankuo] | 有 |
| chuantang | sideng | mugou | — | 有 |
| kaziqiang | sideng | chengzhuan | — | [qiangti] |
| jiaodao | sideng | chengzhuan | — | [qiangti] |
| tingyuan | — | — | — | （`open: true`） |

> `modular` 落为**数组**（如 `["miankuo","jinshen"]`；`houmen` 为 `["miankuo"]`）。

**B2. `packs/siheyuan/dict.json`**：改于前置基线（见 §0），本段未再动。

**缺陷实证（为何必须补）**：

- 改前实测：**siheyuan 基线含 level/material 37 处；jiangnan 基线 0 处**。
- 根因：`room()` 为**全风格共用**实现，读取 `dict["空间角色"][role]` 的属性；江南包 dict 缺这些属性 → **静默丢属性**（装配不报错、字段直接为空）。

#### C. 消费代码 `assemble.mjs`（3 处）

**文件**：`skills/traditional-building/assemble.mjs`（38,854 B）

| # | 位置 | 变更 |
|---|---|---|
| C1 | `assertTypeRefsHitDict`（约 L547） | **扩围**：引用收集规则由「字段名恰为 `ref`」扩为「字段名恰为 `ref`，**或以 `Ref` 结尾**（`wallRef` / `providerRef` / `attachToRef` …）」；同时**跳过 `meta` 段**（其中的 `dictRef` / `rulesRef` 是文件引用而非 dict key，不参与本守卫）。 |
| C2 | `validatePlan`（约 L233） | 签名 `(plan, { rules, type, dict })` → **`(plan, { rules, dict })`**；注明「type 不参与本闸」。 |
| C3 | `validatePlan` 调用点（约 L760） | 同步去掉实参 `type`。 |

> 守卫调用点（约 L591 `assertTypeRefsHitDict(typeDoc, dictDoc)`）为既有逻辑，未变。

**C1 变更后语义**（摘录）：遍历 type 文档，收集所有「非 meta 段内、字段名为 `ref` 或以 `Ref` 结尾、且值为字符串」的引用值，去重后逐个与 dict 全部 key（跳过 `meta` 分类）比对；未命中即抛出：

```
图谱缺陷：类型图谱 ref/*Ref 未命中命名字典：["…"]（角色名/属性须全走 dict key，单一命名权威）
```

#### D. 文档

**D1. 新建** `docs/知识包三件套定义.md`（存档件）

六节：0 一句话 / 1 三者定义（1.1 dict、1.2 type、1.3 rules，含权威原文引注） / 2 归口判据（三问表 + 单一事实源铁律） / 3 依赖关系（**引用图 DAG** 表 + 三要点） / 4 权威对位表 / 5 权威出处列表 / 6 与实例图谱的关系。

核心句：**「词在 dict 定义、结构在 type 组织、约束在 rules 声明；type 与 rules 各自引用 dict，无线性依赖。」**

**D2. 改动** `docs/架构总纲.md`（5 处）

| # | 位置 | 变更摘要 |
|---|---|---|
| D2-1 | L213（判据2） | 「定位与**顺序**严格如下（顺序关系，非依赖堆叠）」→「定位如下（**是「引用图」，非逐级依赖链**：dict 为基座、无上游；type 与 rules 各自 ref dict，rules 的约束可**直连** dict 而不经 type。完整定义与出处见 docs/知识包三件套定义.md）」 |
| D2-2 | L215（type 定义） | 删「结构属性（level/material/modular/structs）**留在 type** 按 ref 挂」→「**不定义对象自身的属性**…**对象自身的属性（等级/材质/模数槽/构造组成等）一律归 dict**（ISO 12006-3：「属性定义对象」）」；对标词改 ISO 23387 data template |
| D2-3 | L229（依据） | 外部标尺重写为 dict↔ISO 12006-3/bSDD、type↔ISO 23387、rules↔IDS 的**逐项对位** + 引用图性质 |
| D2-4 | L234+ | 改为「(a) 已结清…`assertTypeRefsHitDict` 已扩至 `*Ref` 并跳过 meta 段」/「Step 1b + 跨包收敛已执行…实测零漂移、jiangnan 补回 37 处、证伪通过」/「残留（同类未清，非角色名）」/「架构观察（单列待议）」 |
| D2-5 | 同段 | 同步更新残留项与架构观察表述 |

### 2. 验证记录（三项实测，全部通过）

| # | 验证项 | 方法 | 结果 |
|---|---|---|---|
| V1 | **零漂移** | 改后重跑 siheyuan 装配输出，与改动前基线逐行 `diff` | `ZERO_DRIFT_OK`（完全一致） |
| V2 | **属性补回** | 改后重跑 jiangnan 装配，统计 `level` / `material` 出现次数 | **0 → 37**（与 siheyuan 同数），EXIT=0 |
| V3 | **证伪（守卫确实生效）** | 伪造 `_falsify` 包，植入 `center.ref="BOGUS_REF_ZZZ"` 与 `ring.sides.bei.wallRef="BOGUS_WALL_ZZZ"` | 装配抛出 `图谱缺陷：类型图谱 ref/*Ref 未命中命名字典：["BOGUS_REF_ZZZ","BOGUS_WALL_ZZZ"]`，EXIT=1 |

### 3. 消费面核查（现存事实）

- `structs` / `modular` / `family` / `level` / `material` 在 `server/engine`、`web/` 代码中**零消费点**（仅数据文件出现；`geometry.py:438` 仅注释提及 `structs`）。
- `*.type.json` 仅被 `loadKnowledge` 读入，且**只被 `assertTypeRefsHitDict` 校验其 ref**；其组织语义目前不驱动装配（结构事实在 `rules` + `finish()` 内）。
- `refRole` / `attachTo` / `candidateProvider` / `countParam` / `refParam` / `dictRef` / `rulesRef` 全库**无代码消费者**（已随 A 段归一移除）。

### 4. 文件指纹（本轮改动落盘态，2026-09-28 14:48）

| 文件 | 字节 | md5 |
|---|---|---|
| `assemble.mjs` | 38,854 | `6d486c956ceca3e03533b06f2d995ae1` |
| `packs/siheyuan/dict.json` | 16,052 | `d4459342c64eeddfea5e95de2ad608b3` |
| `packs/siheyuan/siheyuan.type.json` | 4,969 | `a3fcddf9682ea5ba4c984b6cec586b7b` |
| `packs/jiangnan/dict.json` | 15,455 | `1bcd3770e57faf3140300425280d27da` |
| `packs/jiangnan/jiangnan.type.json` | 4,588 | `6ad5ff03a4477219a02f63f51e6842c8` |

**git 锚点**：`b8dbe8d docs(架构总纲): 目标态定性 + 5点优化收口 + 知识中心序列化锁JSON(非OWL)`
**git 状态**：6 改 1 新，**均未提交**（`docs/架构总纲.md`、`assemble.mjs`、`packs/{siheyuan,jiangnan}/{dict.json,*.type.json}`、新增 `docs/知识包三件套定义.md`）；`git diff --stat` = 209 insertions / 535 deletions。

### 5. 已知残留 / 未结项（**本轮未处理，留待后续**）

| # | 事项 | 性质 |
|---|---|---|
| R1 | `jiangnan.type.json` 的 `meta.rulesRef: "siheyuan.rules"` —— 与包内实际存在的 `jiangnan.rules` 不一致。结合该包 `meta.desc` 自述「PLACEHOLDER 种子包：复用四合院角色拓扑」，**可能是有意复用，也可能是误配**，未定 | 待定 |
| R2 | `site.children.courtyards` 的 `relation` 与 `ref` 并写（同一关系两处表达）；`countParam` / `refParam` 并写 | 同类未清（非角色名） |
| R3 | `jiangnan.type.json` 的 `meta.type`/`site.type: "siheyuan"` —— 种子包痕迹 | 待定 |
| R4 | `*.type.json` 何时真正驱动装配（现结构事实仍在 `rules` + `finish()` 内） | 架构观察，单列待议 |
| R5 | 本批改动（含前置基线）**尚未提交** | 待人工把关 |

---

## packs v0.2.1 — 2026-09-28

**主题**：`*.type.json` **越界清理**——按 `docs/知识包三件套定义.md` §2 归口判据**逐条**判定（不是整段裁决「归 type 还是 rules」），清掉 type 内混入的「触发 / 缺省 / 同值冗余」条款。

**代码版本**：同 v0.2.0（git `b8dbe8d` + 未提交工作区）。
**线上版本**：未上线。

### 1. 变更明细（两包同步：siheyuan / jiangnan）

判据 = 三问，先命中者定性：①「某词是什么」→ dict；②「一��挂到另一词上」→ type；③「必须 / 禁止 / 值域 / **缺省** / **触发**」→ rules。

**删除**：

| # | 字段 | 命中 | 事实已由何处声明 |
|---|---|---|---|
| 1 | `courtyard.gate.cond: "jin>=2"` | 触发 | `rules.occupancy[waiyuan]` = `at:1, jinGte:2` + `beimen: chuihuamen` |
| 2 | `courtyard.gate.boundary: "between_sequence_1_and_2"` | 位置约束 | 同上（`sequence.naming` 亦证） |
| 3 | `courtyard.peripheral[houzhaofang].cond: "jin>=3"` | 触发 | `rules.occupancy[houzhaoyuan]` = `at:"last", jinGte:3` + `sides.bei: houzhaofang` |
| 4 | `courtyard.ring.sides.<bei/nan/dong/xi>.providerRef`（4 条） | **缺省** | `rules.occupancy` 各进 `sides`。附带实证：type 原「北 = zhengfang」通则在**首进 / 外院不成立**（外院无北房），本身即不准确的通则 |
| 5 | `wall.attrs` 全段（side / kind / provider / height / thickness） | 属性 → dict；值 → rules | side / provider 与 `ring.sides` 重复；kind 与 `rules.wall.taxonomy.围墙.kinds` 重复；height / thickness 与 `rules.norms.wall`（3.3 / 0.4）重复 |
| 6 | `site.type` | 同值两处 | = `meta.type` |
| 7 | `courtyard.ref: "tingyuan"` | 同值两处 | = `courtyard.center.ref` |
| 8 | `courtyard.ring.relation: "weihe"` | 同值两处 | = `courtyard.ring.ref` |
| 9 | `site.children.courtyards.relation: "xulie"` | 同值两处 | = `…ref` |
| 10 | `site.children.courtyards.refParam: "jin"` | 同值两处 | = `…countParam` |

**同时改写**（关键：只删字段不够，事实仍会留在 `desc` 里）：`gate.desc`、`ring.desc`、`ring.sides.*.desc`、`peripheral[houzhaofang].desc` 中原承载的**规则表述**已剥离，改为指向 rules。

**新增**：`meta.scope` —— 声明「本图谱只装无条件的词-词挂载；凡带条件 / 缺省 / 值域者归 rules」，防回归。

**保留（判为 type 合法域，无条件的词-词挂载）**：`center.ref`、`gate.ref`、`peripheral[].ref` + `attachToRef`、`ring.ref`、`ring.sides.*.wallRef`、`site…courtyards{ref, countParam, childType}`、`modularParams.*`、`wall.ref`。

**未动（rules 侧无等价，暂留以免失源）**：`courtyard.peripheral[erfang].cond: "optional"` —— 已加注「待迁入 rules.occupancy 后删 cond」。

### 2. 验证记录

| # | 验证项 | 方法 | 结果 |
|---|---|---|---|
| V1 | JSON 合法 | `JSON.parse` 两文件 | `JSON_OK` |
| V2 | **零漂移** | 改前 / 改后用同一 3 进骨架装配，取输出 md5 | siheyuan `7355b00427f3c91ad8f1925ffe2da17b`、jiangnan `e16b4b4c01365eb5b8a5bf2188861963` —— **改前改后完全一致** |
| V3 | 守卫生效 | 副本包植入 `center.ref = "BOGUS_REF_ZZZ"` | 报 `图谱缺陷：类型图谱 ref/*Ref 未命中命名字典：["BOGUS_REF_ZZZ"]`，EXIT=1 |

> 零漂移的合理性：`*.type.json` **不参与装配**（`validatePlan` 只用 rules/dict；`validateInstanceGraph` 只用其 `ref` 守卫），故清 type 对输出**必然无影响**；唯一变化是守卫覆盖面随字段减少而收窄。

### 3. 文件指纹（2026-09-28 15:2x，**取代 v0.2.0 §4 中两个 type.json 行**）

| 文件 | 行数 | 字节 | md5 |
|---|---|---|---|
| `packs/siheyuan/siheyuan.type.json` | 109（原 137） | 4,637（原 4,969） | `78d73c839bb8291145408a02cc435b9a` |
| `packs/jiangnan/jiangnan.type.json` | 106（原 134） | 4,253（原 4,588） | `d3f4e19b8179f4c632c6ed55787c6749` |
| `assemble.mjs` | — | 38,854 | `6d486c956ceca3e03533b06f2d995ae1`（同 v0.2.0，本轮未动） |

**git 状态**：6 改 2 新（新增 `packs/CHANGELOG.md`、`docs/知识包三件套定义.md`），**均未提交**；`git diff --stat`（仅已跟踪文件）= 225 insertions / 604 deletions。

### 4. 本轮新发现（待议，未处理）

| # | 事项 |
|---|---|
| R6 | `jiangnan.type.json` 与 `siheyuan.type.json` 的 site / courtyard / modularParams / wall 段**逐字相同**（种子包 = 复制品）；其 `meta.rulesRef` 仍指 `siheyuan.rules` |
| R7 | `type.wall.ref = "yuanqiang"` 与 `rules.wall.ref = "yuanqiang_gongqiang"` **不一致** |
| R8 | `rules.wall.taxonomy.围墙.kinds` 列 `[weiqiang, kaziqiang, buqiang, youlang, yingbi]`，但 `finish()` 实际产出 `houyanqiang` —— 两处不对称 |

---

---

## packs v0.2.2 — 2026-09-28

**主题**：**删除江南种子夹具** + 从对外契约中摘除「江南」。知识包目录恢复为**单一 siheyuan**。

**代码版本**：git `b8dbe8d` + 未提交工作区。
**线上版本**：未上线。

### 1. 删除内容

| 对象 | 说明 |
|---|---|
| `packs/jiangnan/`（`dict.json` / `jiangnan.rules` / `jiangnan.type.json`） | 2026-09-27 由 `21832df`「服务端 packs 参数化」引入的**种子夹具**，用途仅为证明 packs 可参数化。其自述见 `jiangnan.rules` meta：「PLACEHOLDER 种子包：类型学与四合院同构」「仅证明多包机制」。type 段与 `siheyuan.type.json` **逐字相同**；rules 仅 49 行占位数值差异（`modus` 3.3→3、`taiming` 0.3→0.45、`gateSpan` 3.0→3）。**不含任何江南建筑知识。** |

**删除动因**：`SKILL.md` 规定「可用风格清单 = `packs/` 下的目录名」，而 `SKILL.md` 与 `agent.yaml` 又把「江南民居」列为可识别风格 → 该夹具的存在使 LLM 会把「江南」当真风格，加载后产出**穿江南外衣的四合院**（静默错风格、不报错）。当前重心是先把四合院梳理好，故整体清除。

### 2. 契约同步（3 处）

| 文件 | 原 | 现 |
|---|---|---|
| `SKILL.md` frontmatter `description` | 「（四合院 / 江南民居 / …）」 | 「（当前支持四合院）」 |
| `SKILL.md` ① 理解层风格推断条 | 「「江南 / 徽派 / 天井院」→ 对应包」 | 「当前 `packs/` 下只有 `siheyuan` 一个包…不要臆造 style」 |
| `agent.yaml` system | 「（四合院、江南民居等）」 | 「（当前支持四合院）」 |

> 「单专家 · 多包」的**架构表述保留**——可插拔机制不变，只是当前只有一个包。`docs/架构总纲.md` L189-191 的「江南 / 阿房宫」保留为**机制论证举例**；L198 的「已落地 / 规划」清单已按实盘修正。

### 3. 验证记录

| # | 验证项 | 结果 |
|---|---|---|
| V1 | 目录 | `packs/` 仅 `siheyuan/` + `CHANGELOG.md` ✓ |
| V2 | **siheyuan 零漂移** | 3 进骨架装配 md5 `7355b00427f3c91ad8f1925ffe2da17b`，与删除前**一致** ✓ |
| V3 | `--style jiangnan` | ENOENT（`packs/jiangnan/jiangnan.rules` 不存在），EXIT=1 |
| V4 | 可恢复性 | 删除内容完整保留在 git `21832df`，`git checkout 21832df -- <path>` 可恢复 |

⚠️ **V3 暴露的缺口（未修）**：`loadKnowledge` 对未知 style 抛的是**裸 Node ENOENT 栈**，而非「图谱缺陷：…」友好提示——LLM 若推断出不存在的 style 会收到不可读错误。建议补一条「未知风格 X；`packs/` 下可用：…」（本轮未改，待指令）。

### 4. 影响面：v0.2.0 / v0.2.1 中对江南的改动随之作废

v0.2.0 的「`packs/jiangnan/dict.json` 补 15 条属性 + 新增 `tingyuan`」、v0.2.1 的「`jiangnan.type.json` 同步归一」两项**随包删除而失效**（历史条目按本存档约定**不追改**，仅在此声明）。`siheyuan` 侧同名改动**继续有效**。

---

---

## packs v0.2.3 — 2026-09-28

**主题**：**`rules.wall` 接上消费者**——④ 按 `ring.<side>.kind` 取墙种高/厚；`wall.kinds` / `wall.taxonomy` 由死数据转为值域权威，**外围围墙声明的 3.6 首次生效**。

**代码版本**：git `b8dbe8d` + 未提交工作区。
**线上版本**：未上线。

### 1. 背景：`rules.wall` 此前是死段

逐段 grep 核实：`rules` 的 `occupancy` / `position` / `paramRanges` / `sequence.naming` / `usage` / `norms` 均有代码消费者，**唯 `wall` 整段（`model` / `base` / `ref` / `taxonomy` / `kinds` / `boundarySegment`）零消费**。后果：`wall.kinds.weiqiang.height = 3.6`（外围围墙）从未生效——④ 统一取 `norms.wall.height = 3.3`，外圈院墙一直矮 0.3m（而 `norms.wall.desc` 早已自认「外围围墙可略高(3.6m)」）。

### 2. 变更明细（3 文件）

| # | 文件 | 变更 |
|---|---|---|
| A | `assemble.mjs` `snapshotRules` | 快照增带顶层 `wall.kinds`（墙种高厚值域）+ `wall.taxonomy`（墙种分组）。此前 `appliedRules` 仅 4 键（`norms` / `paramRanges` / `occupancy` / `position`），④ 根本拿不到 `wall`。 |
| B | `server/engine/geometry.py` `compute_geometry` | 取 `appliedRules.wall.kinds` → `wall_kinds`、`taxonomy.围墙.kinds` → `ring_kinds`，传入 `_geo_wall_ring`。 |
| C | `server/engine/geometry.py` `_geo_wall_ring` | 新增 `side_h_t(side)`：该侧 `ring.<side>.kind` **属「围墙」类**时取 `wall_kinds[kind].height/thickness`，否则回落 `norms.wall`；北/南/东/西四侧各按自身 kind 取；`ns_wall` 增 `side` 形参。 |
| D | `packs/siheyuan/siheyuan.rules` | 修悬空 ref：`wall.ref` `"yuanqiang_gongqiang"` → `"yuanqiang"`（`yuanqiang_gongqiang` 不在 dict，属悬空引用）。 |

**关键设计（踩过的坑）**：`_geo_wall_ring` 画的是**基底院墙**（随后由 `_resolve_boundary` 按建筑真实覆盖做区间相减）。`houyanqiang` 属「建筑用墙(非围墙)」，其 `thickness = 0.3` 是**建筑后檐墙**的厚度、不是院墙的——若照取，被部分替换后的残留段会变成 0.3 的薄墙。故**限定只认「围墙」类**（`taxonomy.围墙.kinds` = weiqiang / kaziqiang / buqiang / youlang / yingbi），`houyanqiang` 回落 `norms.wall`。这也顺带让 `wall.taxonomy` 由死数据变成判据来源。

### 3. 验证记录（4 项）

| # | 验证项 | 方法 | 结果 |
|---|---|---|---|
| V1 | **回落路径零漂移** | 旧实例（`appliedRules` 无 `wall`）+ 新代码跑 ④⑤ | md5 `753cf43cf052196b650648c08f25cd9c`，与改动前基线**完全一致**（缺 `wall_kinds` 时行为不变） |
| V2 | 新路径生效 | 新装配实例（`appliedRules` 含 `wall`）跑 ④⑤ | boxes **4883 → 4883**（总数不变）；`yuanqiang` 高度分布 `{0.55: 372}` → `{0.55: 234, 0.6: 138}` |
| V3 | **差异逐条归因** | baseline 与新输出按序逐条比对 | **changed = 138**，全部为 `yuanqiang` `h` 0.55→0.6；其余变化字段仅 `y`（138 个），偏移 **6 档 `[0.025, 0.075, 0.125, 0.175, 0.225, 0.275]`** 与 6 层墙逐层吻合（第 k 层 Δy = 0.05k + 0.025）；**`w` / `d` 零变化** |
| V4 | 语义修正有效 | 修正前（误取 houyanqiang）vs 修正后 | 修正前多出 102 个 `w`/`d` 变化（薄墙残留），修正后归零 |

**影响面**：装配输出 md5 变了（`7355b004…` → `2c6d0c9a…`）——因 `appliedRules` 新增 `wall` 段（实例体积 +约 1KB）；几何侧是**有意的 138 体素变高**，非漂移。

### 4. 文件指纹（2026-09-28 16:0x）

| 文件 | 字节/行 | md5 |
|---|---|---|
| `assemble.mjs` | 39,416（原 38,854） | `b77ad183e48f6c09122fc86c59e3f8e7` |
| `server/engine/geometry.py` | 966 行 | `2f34e6553e8f767b2efc0f07ad3a9517` |
| `packs/siheyuan/siheyuan.rules` | 21,409（原 21,419） | `7cdec515ff37fe857667889f6202c10f` |
| 装配输出（3 进骨架） | — | `2c6d0c9ae26dbddab1881b02dd4765d4`（原 `7355b004…`） |

### 5. 消费面变化

`rules.wall` 由**死段 → 活段**（`kinds` 供 ④ 取值域、`taxonomy` 供 ④ 判分组）；`c.ring.*.kind` 亦首次被 ④ 消费（`ring.provider` 仍不读）。`rules.wall` 内仍无消费者：`model` / `base` / `ref`（`ref` 已修正为合法值，但无代码读）、`boundarySegment`（描述性）。

---

### 6. 附：知识包文件清单（现状）

```
packs/
├── CHANGELOG.md                  ← 本存档
└── siheyuan/
    ├── dict.json                 16,052 B  词汇层（唯一命名权威）
    ├── siheyuan.rules            21,409 B  约束层（内容为 JSON，后缀为 .rules）
    └── siheyuan.type.json         4,637 B  结构层
```

> 注：`*.rules` 文件实为 JSON 文本，`meta` 含 `dictRef` / `typeRef`（反向引用同包 dict 与 type）。

---

## packs v0.3.0 — 2026-09-28

**主题**：**形体原型（form）声明化 + 引擎零风格硬编收口**。把「一栋房/一道门长什么样、怎么摆」「哪一进算什么院」「这侧墙算什么墙种」从不变件（`geometry.py` / `assemble.mjs`）搬进知识包，代码只按声明求值。

**版本口径**：`v0.Y` 为**归口/结构级**改动——本条属之（知识包新增 `form` / `color` 结构、rules 新增三段声明；消费代码随之零硬编）。

**代码版本**：git `b8dbe8d`（基线）+ **本轮改动未提交**（工作区状态，指纹见 §4）。
**线上版本**：**未上线**（`building-wiki-012` 部署于 2026-09-20，不含本改动）。

### 1. 动因（架构判据，非偏好）

总纲 §7 判据 1「**引擎零风格硬编**：不出现任何具体建筑类型 / 角色名 / 进数 / 拓扑字面量」。
本轮把该判据从「靠人记住」变成「可重复的机器检查」——见 `tools/kb/check_hardcode.py`（§3 V5）。

### 2. 变更明细

#### A. dict：每个词条声明「形体原型」与「图示色」

新增两个**对象固有属性**（依据 ISO 12006-3「属性定义对象」→ 归 dict）：

```json
"zhaimen":  { "form": {"kind":"gate-passage","at":"east-end","tower":true},  "color": "#8B4513", ... }
"houmen":   { "form": {"kind":"gate-passage","at":"west-end","tower":false}, "color": "#999999", ... }
"zhengfang":{ "form": {"kind":"room"},  "color": "#C0504D", ... }
"yuanqiang":{ "form": {"kind":"ring-wall"}, "color": "#7F7F7F", ... }
"tingyuan": { "form": {"kind":"void"},  "color": "#CFCFCF", ... }
"taiji"(构件):{ "form": {"kind":"base"}, "color": "#9E9284", ... }
```

- `kind` 取值域：`room`(房屋) / `gate-passage`(门道) / `colonnade`(柱廊) / `screen-wall`(屏墙) /
  `ring-wall`(环墙·标独立院墙) / `base`(台基) / `void`(虚空·不产构件) / `passage`(通行做法·不产构件)。
- `at = east-end / west-end / center`：门落在墙环哪端；`tower: bool`：是否带门楼。
- 共 19 个词条补 `form` + `color`；`color` 取代 `geometry.py` 里原有的 `ROLE_COLORS` 硬编色表。

#### B. rules：新增三段声明 + 四处键名去角色化

| # | 新增/改动 | 替代的原硬编 |
|---|---|---|
| B1 | `sequence.courtRole = { anchor{side,role}, roles{anchor,before,after,single}, usageCourtRole }` | `assemble.mjs finish()` 里 `"zhengfang"/"guoting"/"neiyuan"/"waiyuan"/"houzhaoyuan"/"tingyuan"/"tingfangyuan"` |
| B2 | `wall.assign = { withBuilding, standalone, withGate }` | `finish()` 里 `"kaziqiang"/"houyanqiang"/"weiqiang"` |
| B3 | `usage[0].slot = { court: 2, side: "bei" }` | `finish()` 里中文槽位 `"erjinyuan_zhengwei"`（含进数+方位） |
| B4 | `wall.taxonomy.<组>.appliesTo = "ringBase" / "buildingPart"` | ④ 里靠中文字面量 `"围墙"` 判「哪组墙种决定基底院墙高厚」 |
| B5 | `norms.room.baseRole = "taiji"` | `_geo_room` 里 `"taiji"`；原代码已部分声明，本轮补全 |
| B6 | `wall.ref = "yuanqiang"` | `_resolve_boundary` / `_geo_wall_ring` 里 `"yuanqiang"` |
| B7 | `norms.room.miankuoDefault = 5` / `jinshenDefault = 3` / `norms.door.at = "mingjian"` | 装配器 `room()` 里字面量 `5 / 3 / "mingjian"` |
| B8 | `norms.layout.xiangfang` → **`norms.layout.wing`** | 键名由「角色名」改为「形体原型级」（④ 只认原型，不认角色） |
| B9 | `norms.zhaimen.eastMargin` / `norms.houmen.westMargin` → 统一 **`margin`** | 方向由 `dict.<门>.form.at` 给——**同一事实只允许一处表达** |

#### C. 消费侧（代码）随之去掉硬编

- `geometry.py`：删 `ROLE_COLORS`；新增 `_entry_of` / `_form_of` / `_hex_to_int` / `_colors_from_applied`；
  三个按角色名硬判的门/房分支（`_geo_wing` / `_geo_daozuo` / `_geo_back_gate`）合成
  **一个按声明分派的通用入口** `_geo_house`（有 `gate` → 门道房；`chuantang` → 明间贯通；否则普通房间）。
- `assemble.mjs`：`ROOM_DECL_KEYS` 仍在（骨架 schema，非角色名）；`finish()` 改读 B1/B2/B3 三段声明；
  院心角色 / 院墙关系改读 **type 图谱** `courtyard.center.ref` / `courtyard.ring.ref`（**type 首次真正驱动装配**）。
- `assemble.mjs` 的**默认风格字面量 `"siheyuan"` 删除**：`style` 改为**必填**，缺即报「图谱缺陷」并列出可用包；
  `loadKnowledge` 对未知风格改报「未知风格…（可用：…）」而非裸 ENOENT 栈。

#### D. 附属知识快照：由「按需裁剪」改为**三件套整份**

按总纲 §4「衔接三要素」第 3 条：实例图谱嵌 `appliedRules` / `appliedType` / `appliedDict` **整份**。
删掉原裁剪实现及其两张硬编键名清单（`NORMS_ALWAYS` 原型键 + 四个角色名前缀）、`DICT_FULL_KEEP` 补丁。
副带收益：裁剪会**裁掉合法词**，使下游报错里列出的合法集不完整——该整类问题结构性消失。

### 3. 验证记录（6 项）

| # | 验证项 | 方法 | 结果 |
|---|---|---|---|
| V1 | **④ 重构语义等价** | `tools/kb/_verify_form_refactor.py`：把重构前 `geometry.py` 的原文逻辑逐字抄写，与现役实现做**顺序无关集合**比对 | 5 例（jin 1/2/3/4 + jin3-houmen）老/新构件集合**全部相等** |
| V2 | **零漂移（全链）** | `tools/kb/baseline.py --check` | ⑤ 体素 sha1、④ 构件集合、role 分布、sku **逐项一致**；仅 `instance_sha1` 变（D 的快照变宽，刻意） |
| V3 | **独立交叉验证** | 与早于本批改动的真实产物 `tools/preview/out/boxes.json`（2026-09-28 22:49）对撞 | **几何 100% 相同**；唯一差异是两处 label 由拼音改中文（`taiji`→台基 818 块、`yuanqiang`→院墙 102 块），即既有债务「中文名硬编清零」的既定修正 |
| V4 | `jin=4` 过厅路径 | jin4 走 `usage.slot` + `usageCourtRole` 分支 | 构件集合零漂移 → B1/B3 的新路径与旧 `"erjinyuan_zhengwei"` 分支**逐构件一致** |
| V5 | **机器判据 + 证伪** | `tools/kb/check_hardcode.py`（扫不变件字面量 ∩ 所有 pack 的 dict key 全集） | 两项受检文件 **0 处**，rc=0；**证伪**：故意植入 `zhengfang/chuihuamen/kaziqiang/guoting/houzhaoyuan/qingzhuan` → 6 处**全部捕获**，rc=1 |
| V6 | fail-fast 语义 | 喂未知风格 `jiangnan` / 违规骨架（首进北侧放垂花门） | 报「图谱缺陷：未知风格「jiangnan」…（可用：siheyuan）」/「四至「nan」应为 daozuofang…（occupancy.waiyuan 约束）」，均 rc≠0 |

### 4. 文件指纹（2026-09-28 本轮末）

| 文件 | 行数 | md5 |
|---|---|---|
| `assemble.mjs` | 835 | `8ca988b8d18a6b2862260c7e507b2180` |
| `server/engine/geometry.py` | 1017 | `9f95a11fe15802cf86fa5d7e1f2bb2ae` |
| `packs/siheyuan/siheyuan.rules` | — | `112fcccf3ac75ca6c174156e5b0a41b1` |
| `SKILL.md` | — | `4c6db64d9fd70bb34ba81b99c29bedf1` |

**影响面**：装配输出 `instance_sha1` 变了（快照宽度 + dict 新增 `form`/`color` + rules 新增三段）；
样本体积 29KB → 36KB。**几何与体素输出零漂移**（V1–V4 四路证据）。上游 MCP 入参仍走 `cos:` 引用，不受体积影响。

### 5. 未结

- `rules.orientation` 仍无消费者（仅 `SKILL.md` 提名）。
- `courtyard.peripheral[erfang].cond: "optional"` 仍是 type 侧唯一越界残留（rules 无等价声明，删则失源）。
- 形体原语尚无 `slope`（坡屋顶）——当前屋顶按平板处理。
- **知识包源（`src/*.md`）尚未覆盖全量三件套**：编译器目前是「源可 1:1 还原现有三件套」的**校验器**，
  不是生成器（仅 chuihuamen / courtyard / zhengfang 三篇）。「源成为唯一权威」待办。
