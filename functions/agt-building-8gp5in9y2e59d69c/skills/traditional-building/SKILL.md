---
name: traditional-building
description: 把用户对中国传统建筑的自然语言需求（当前支持四合院），转成「实例图谱」再算成 3D 体素模型。用于任何「建一座 N 进院 / 加个影壁 / 换个风格」这类建模请求。单专家多包：风格差异全部由知识包承担，技能本身不写死任何风格事实。
---

# 中国传统建筑 · 实例图谱智能化（单专家 · 多包）

## 你在这条链上的位置

```
用户自然语言
   │
   ├─ 你（LLM）：① 理解 —— 推断风格 + 产「骨架」（纯 role + 业务量，零坐标/几何量）
   │        ↓
   ├─ assemble.mjs（确定性查表装配，含实例图谱硬闸：四至/门位违规即时报错）：骨架 → 自包含实例图谱
   │        ↓
   ├─ upload_instance.mjs：实例 → cos:instances/<uuid>.json（上传云存储）
   │        ↓
   └─ 你调用 MCP 工具 generate_building(instance_ref="cos:<key>")
            → ④⑤ 一体化：图谱 → 构件 → 体素 BOX → 返回 boxes
```

**你是整条链路的总控（全 Agent 形态）：理解 + 装配 + 上传 + 调用 `generate_building` 全由你完成；前端只负责拿结果渲染。**
**红线不变：你依旧不碰坐标 / 几何量**——④⑤ 的计算在 MCP 侧，你只传「引用」、收「结果」。

## ① 理解层：先定风格，再出骨架

本技能支持多种风格（知识包），风格差异**全部在知识包里**，技能代码零风格事实。

- **风格（style）由你推断**：从用户话术判断（如「四合院 / 北京院子」→ `siheyuan`）。**本地 `packs/`（仓库顶层）目前只有 `siheyuan` 一个包**；运行时 assemble 按 `cos:packs/manifest.json` 拉取对应版本——用户要的风格若无对应包，如实告知暂不支持，**不要臆造 style**（缺包会报「图谱缺陷：未知风格…」并列出可用包）。
- 把推断出的风格写进骨架顶层字段 **`style`**（如 `"style": "siheyuan"`）。`assemble.mjs` 会据此加载 `packs/<style>/` 知识包。
- **`style` 是必填项**：装配器**不设默认风格**（默认风格字面量＝把具体建筑类型写进引擎，违反总纲 7 判据 1）。用户没明说风格时，你要**自行判断并在骨架里写明**——当前只有四合院一个包，所以默认写 `siheyuan`；但必须写出来，漏了会直接报错。
- 可用风格清单 = 仓库顶层 `packs/` 下的目录名（本地 authoring 用）；运行时等价于 `cos:packs/manifest.json` 里的风格键。需要时先 `ls packs/` 确认有哪些包。

## 硬约束（违反即作废）

1. **不碰坐标 / 几何量**——坐标、朝向、镜像、法向量，以及「由尺寸推坐标」的运算，一个都不要算、不要写。
   你只声明「哪一侧有什么建筑、门开在哪」（role + 拓扑）。业务量（进数、面阔、进深…）的**默认值与
   合法值域一律取自对应知识包**（`packs/<style>/<style>.rules:paramRanges`、`<style>.type.json`）——无依据不写，写了须落在域内。
2. **role 只能取知识包词表里的 key**，不得自造、不得写中文、不得写别的形式。
   词表 = `packs/<style>/dict.json` 的「空间角色」段。
3. **不要写院名**（外院/内院/后罩院…）——由 `<style>.rules:sequence.naming` 推导。你只给 `sequence`。
4. 不要输出坐标、方向向量、镜像等几何动作。
5. `courtyards` 条目数必须**正好等于** `jin`，`sequence` 从 1 连续到 jin。

## 骨架格式（严格 JSON）

```json
{
  "style": "siheyuan",            // ① 推断出的风格（**必填**，无默认值；漏了装配器直接报错）
  "jin": 3,
  "courtyards": [
    {
      "sequence": 1,
      "enclosure": {
        "nan":  {"role": "<词表key>", "gate": {"role": "<词表key>"}},
        "bei":  {"role": "<词表key>", "gate": {"role": "<词表key>"}},
        "dong": {"role": "<词表key>"},
        "xi":   {"role": "<词表key>"},
        "beimen": {"role": "<词表key>"}
      },
      "perimeter": true,
      "peripheral": [{"role": "<词表key>"}]
    }
  ]
}
```

- `nan`/`bei`/`dong`/`xi` = 该侧建筑；`gate` = 嵌在它身上的门（宅门嵌在倒座房上）
- **可选业务量**：某侧建筑可带 `miankuo`（开间数，如 `{"role":"zhengfang","miankuo":7}`）；
  合法值域见 `<style>.rules:paramRanges.miankuo`，不写则取该 role 的缺省。只声明**你确知**的量，别硬编。
- `beimen`/`nanmen` = 该院墙上的门本体（垂花门）
- `perimeter` = 有院墙，通常 true；`peripheral` = 附属物（影壁等），可选

## 规制（必须先读，别凭印象）

读 `packs/<style>/<style>.rules` 对应段（它们是该风格唯一的事实源）。以 siheyuan 为例，各风格结构一致：

- `occupancy` —— **院落四至默认构成**：「每一进，哪一侧放什么角色」的**唯一事实源**。
  **出骨架前逐字读完**。逐条按 `at`（`1`=首进 / `"middle"`=中间进 / `"last"`=末进）+ `jinEq` / `jinGte` 命中，首个命中者胜出。
- `position` —— **补充约束**（只放 `occupancy` 装不下的）：后门默认不设，仅用户明说「宅后临街」才加；穿堂仅 jin≥3 时由正房明间做。
  门位与四至构成的事实源都在上面 `occupancy` 段，此处不再重复。
- `orientation` —— 朝向
- `usage` —— 用途（如四进院第二进正位房作过厅）
- `sequence.naming` —— 院名推导规则

**下面这几段由装配器自动消费，你不需要读、更不要在骨架里声明**（它们决定的是「场景长什么样」，
不是「你要摆什么」）：`sequence.courtRole`（哪一进算什么院：外院/内院/厅房院/后罩院/庭院）、
`wall.assign`（每侧墙算什么墙种）、`norms`（全部规制数值：面阔/进深/高/台明/门洞/墙厚…）。
你只给 role + 拓扑，这些一律由知识包与装配器补齐。

## 怎么装配

你的工作目录（cwd）里已有这个 skill，路径固定：

```bash
# 1) 先把骨架写成文件（例如 sk.json，含顶层 "style" 字段）
# 2) 跑装配器（风格必给：取骨架里的 style，或用 --style 覆盖；--packs 默认脚本同目录 packs）
node .claude/skills/traditional-building/assemble.mjs --style siheyuan --skeleton sk.json > instance.json
# 也可省略 --style，由骨架 style 字段决定（二者必须有一个，缺了就报错）：
node .claude/skills/traditional-building/assemble.mjs --skeleton sk.json > instance.json
# 也支持 stdin：cat sk.json | node .claude/skills/traditional-building/assemble.mjs --style siheyuan
```

### CLI 只认三个参数

`--packs`（**不传 = 运行时从 COS 按 manifest 拉取知识包**；传则指向本地 packs 根，如仓库顶层 `packs/`）、`--style`（骨架 `style` 的同义覆盖，二者必须有一个）、`--skeleton`。

### 运行时拉取（知识库动态化）
- 装配器 `assemble.mjs` 在**不传 `--packs`** 时，按 `cos:packs/manifest.json` 解析该风格版本与 base，再从 COS 拉取 `rules/type/dict` 三件套（按版本落到 `/tmp` 缓存，warm 容器免重复拉取）。
- 因此**知识更新只需重跑 `tools/kb/publish_pack.mjs` 上传到 COS**，无需 redeploy 函数。
- 本地 authoring / 回归用 `--packs <本地 packs 根>` 走本地包，不依赖云。
**传别的参数一律报错**（不静默忽略）——所以别自造开关。

**变体靠骨架表达，不靠命令行**：用户说「不要影壁」，就把它从该进的 `peripheral` 里去掉；
说「外院不要厢房」这类**违反规制**的要求，不要靠删字段凑——它会被装配出口硬闸按 `occupancy` 拒掉，
应改为如实告知用户该形制不合外院规制。

若路径不确定，先定位脚本：`find . -name assemble.mjs -path '*traditional-building*'`。

输出 = **自包含实例图谱**（`meta` / `data` / `appliedRules` / `appliedType` / `appliedDict`）。
它把本风格知识中心**三件套整份**（dict 词汇层 / type 结构层 / rules 约束层）嵌进实例，
**下游不再需要知识包**。

## 怎么出模型（全 Agent 形态）

装配出实例图谱后，**不要**把它打印出来——改为上传云存储，再让 MCP 在你这一侧把 ④⑤ 跑完：

```bash
# 1) 装配（--style 由骨架 style 决定，无需手传）
node .claude/skills/traditional-building/assemble.mjs --skeleton sk.json > instance.json
# 2) 上传，拿到 cos:<key> 引用（凭据来自 TCB_SECRET_ID/KEY，临时凭据再补 TCB_TOKEN）
node .claude/skills/traditional-building/upload_instance.mjs --file instance.json
#    -> 输出形如：cos:instances/<uuid>.json
```

拿到 `cos:instances/<uuid>.json` 后，调用 MCP 工具（名字带 mcp 前缀，即 `mcp__building-wiki__generate_building`）：

```json
{ "instance_ref": "cos:instances/<uuid>.json" }
```

它会在 MCP 侧读回实例 → 跑 ④ compute_geometry → 跑 ⑤ geometry_to_boxes →
**返回体素 BOX 清单**（含坐标；harness 对超大输出会持久化为引用返回）。
（④⑤ 是这一个工具的内部步骤，MCP 侧不重载知识包——它只吃实例图谱自带的
appliedRules / appliedType / appliedDict 三件套快照。
实例图谱的合规硬闸只在你这一侧（装配出口）做一次；MCP 侧只剩 ④ 自带的形状闸，入参不是自包含图谱即报错。）
把这个结果（或它给的引用）作为你的最终输出即可——**前端会据此渲染**。

**为什么传引用不传值**：实例图谱 ~10KB，若走工具入参通道会被 harness 截断损坏
（已实测：参数到达时变成 list 或非法 JSON 字符串，pydantic 直接拒）。所以先上传拿 `cos:` 引用、再让 `generate_building` 按引用读回——绕开这条 10KB 通道。

**出错时不要自己编几何/坐标**——那是踩红线。实例图谱有两道**自动化硬闸**（确定性代码、不靠你判断），
报错一律以「图谱缺陷：…」开头，且**精确点名哪进 / 哪侧 / 哪个角色违规**，照着改骨架即可：

- **第一道（assemble.mjs 装配出口）**：装配完立刻校验「四至构成(occupancy) + 门位(position) + 词表 + 值域」。
  违规在本地 fail-fast，省掉后面 55s 的 MCP 往返。
- **第二道（generate_building 读回实例后）**：服务端用同一契约再校验一次，把不合规图谱挡在 ④⑤ 之前。

常见「图谱缺陷」与改法：
- `第 k 进 四至「bei」应为 zhengfang，实际为 …（occupancy.xxx 约束）` → 该进四至构成错，回去读 `occupancy` 里 k 命中的那条规则。
- `垂花门(二门)只应设于首进北界` / `后门(houmen)只应设于末进…` → 门位违反 `position`；**后门默认不设**，仅用户明说「宅后临街」才加。
- `角色 … 不在合法词表` → role 拼错或杜撰，改回 `dict.json「空间角色」`里的 key。
- `jin=N 超出 paramRanges.jin 值域` → 进数超范围（当前上限见对应包 paramRanges）。

把 `图谱缺陷` 原文读回来，改骨架 → 重跑 `assemble.mjs` → 上传 → 调 `generate_building`。
临时凭据报 403 时，确认 `TCB_TOKEN` 已注入（同进程 env）。
