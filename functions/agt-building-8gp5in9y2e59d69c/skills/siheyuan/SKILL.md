---
name: siheyuan
description: 把用户对北京四合院的自然语言需求，转成「实例图谱」再算成 3D 体素模型。用于任何「建一座N进四合院 / 加个影壁 / 不要游廊」这类建模请求。
---

# 北京四合院 · 实例图谱智能化

## 你在这条链上的位置

```
用户自然语言
   │
   ├─ 你（LLM）：只产「骨架」——纯 role + 业务量，零坐标/几何量
   │        ↓
   ├─ assemble.mjs（确定性查表装配，含实例图谱硬闸：四至/门位违规即时报错）：骨架 → 自包含实例图谱
   │        ↓
   ├─ upload_instance.mjs：实例 → cos:instances/<uuid>.json（上传云存储）
   │        ↓
   └─ 你调用 MCP 工具 generate_building(instance_ref="cos:<key>")
            → ④⑤ 一体化：图谱 → 构件 → 体素 BOX → 返回 boxes
```

**你是整条链路的总控（全 Agent 形态，2026-09-22 架构决策）：理解 + 装配 + 上传 +
调用 `generate_building` 全由你完成；前端只负责拿结果渲染。**
**红线不变：你依旧不碰坐标 / 几何量**——④⑤ 的计算在 MCP 侧，你只传「引用」、收「结果」。

## 硬约束（违反即作废）

1. **不碰坐标 / 几何量**——坐标、朝向、镜像、法向量，以及「由尺寸推坐标」的运算，一个都不要算、不要写。
   你只声明「哪一侧有什么建筑、门开在哪」（role + 拓扑）。业务量（进数、面阔、进深…）的**默认值与
   合法值域一律取自知识中心**（`siheyuan.rules:paramRanges`、`siheyuan.type.json`）——无依据不写，写了须落在域内。
2. **role 只能取知识中心词表里的 key**，不得自造、不得写中文、不得写别的形式。
   词表 = `<skill>/knowledge/dict.json` 的 **「空间角色」** 段（18 条）。
3. **不要写院名**（外院/内院/后罩院…）——由 `siheyuan.rules:sequence.naming` 推导。
   你只给 `sequence`。
4. 不要输出坐标、方向向量、镜像等几何动作。
5. `courtyards` 条目数必须**正好等于** `jin`，`sequence` 从 1 连续到 jin。

## 骨架格式（严格 JSON）

```json
{
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
  合法值域见 `siheyuan.rules:paramRanges.miankuo`，不写则取该 role 的缺省。只声明**你确知**的量，别硬编。
- `beimen`/`nanmen` = 该院墙上的门本体（垂花门）
- `perimeter` = 有院墙，通常 true；`peripheral` = 附属物（影壁等），可选

## 规制（必须先读，别凭印象）

读 `<skill>/knowledge/siheyuan.rules` 的这几段，它们是你唯一的事实源：

- `occupancy` —— **院落四至默认构成**：「每一进，哪一侧放什么角色」的**唯一事实源**。
  **出骨架前逐字读完**。逐条按 `at`（`1`=首进 / `"middle"`=中间进(1<k<jin) / `"last"`=末进）
  + `jinEq` / `jinGte` 命中，首个命中者胜出——与你推导院名用的是同一套求值律。
  ⚠️ **各进并不同构**（首进的构成与中间进、末进都不同）：按每进各自命中的那条规则出骨架，
  绝不要把某一进的构成套用到其余进。
- `position` —— 各构件的**位置约束**（垂花门只在一↔二进之间；后罩房只在末进；宅门只在首院倒座；**后门默认不设**，仅当用户明确说「宅后临街」才加）
- `orientation` —— 朝向
- `usage` —— 用途（如四进院第二进正位房作过厅）

## 怎么装配

你的工作目录（cwd）里已有这个 skill，路径固定：

```bash
# 1) 先把骨架写成文件（例如 sk.json）
# 2) 跑装配器（--knowledge 默认就是脚本同目录的 knowledge，不用传）
node .claude/skills/siheyuan/assemble.mjs --skeleton sk.json > instance.json
# 也可 stdin：cat sk.json | node .claude/skills/siheyuan/assemble.mjs
```

若路径不确定，先定位脚本：`find . -name assemble.mjs -path '*siheyuan*'`。

输出 = **自包含实例图谱**（`meta` / `data` / `appliedRules` / `appliedDict`）。
它自带本次用到的规则与字典，**下游不再需要知识中心**。

## 怎么出模型（全 Agent 形态）

装配出实例图谱后，**不要**把它打印出来——改为上传云存储，再让 MCP 在你这一侧把
④⑤ 跑完：

```bash
# 1) 装配（--knowledge 默认脚本同目录 knowledge，不用传）
node .claude/skills/siheyuan/assemble.mjs --skeleton sk.json > instance.json
# 2) 上传，拿到 cos:<key> 引用（凭据来自 TCB_SECRET_ID/KEY，临时凭据再补 TCB_TOKEN）
node .claude/skills/siheyuan/upload_instance.mjs --file instance.json
#    -> 输出形如：cos:instances/<uuid>.json
```

拿到 `cos:instances/<uuid>.json` 后，调用 MCP 工具（名字带 mcp 前缀，
即 `mcp__building-wiki__generate_building`）：

```json
{ "instance_ref": "cos:instances/<uuid>.json" }
```

它会在 MCP 侧读回实例 → 跑 ④ compute_geometry → 跑 ⑤ geometry_to_boxes →
**返回体素 BOX 清单 JSON**（含坐标；harness 对超大输出会持久化为引用返回）。
把这个结果（或它给的引用）作为你的最终输出即可——**前端会据此渲染**。

**为什么传引用不传值**：实例图谱 ~10KB，若走工具入参通道会被 harness 截断损坏
（已实测：参数到达时变成 list 或非法 JSON 字符串，pydantic 直接拒）。所以先上传拿
`cos:` 引用、再让 `generate_building` 按引用读回——绕开这条 10KB 通道。

**出错时不要自己编几何/坐标**——那是踩红线。实例图谱现在有两道**自动化硬闸**（确定性代码、不靠你判断），
报错一律以「图谱缺陷：…」开头，且**精确点名哪进 / 哪侧 / 哪个角色违规**，照着改骨架即可：

- **第一道（assemble.mjs 装配出口）**：装配完立刻校验「四至构成(occupancy) + 门位(position) + 词表 + 值域」。
  违规在本地 fail-fast，省掉后面 55s 的 MCP 往返。
- **第二道（generate_building 读回实例后）**：服务端用同一契约再校验一次，把不合规图谱挡在 ④⑤ 之前。

常见「图谱缺陷」与改法：
- `第 k 进 四至「bei」应为 zhengfang，实际为 …（occupancy.xxx 约束）` → 该进四至构成错，回去读 `occupancy` 里 k 命中的那条规则。
- `垂花门(二门)只应设于首进北界` / `后门(houmen)只应设于末进…` → 门位违反 `position`；**后门默认不设**，仅用户明说「宅后临街」才加。
- `角色 … 不在合法词表` → role 拼错或杜撰，改回 `dict.json「空间角色」`里的 key。
- `jin=N 超出 paramRanges.jin 值域` → 进数超范围（当前上限 4）。

把 `图谱缺陷` 原文读回来，改骨架 → 重跑 `assemble.mjs` → 上传 → 调 `generate_building`。
临时凭据报 403 时，确认 `TCB_TOKEN` 已注入（同进程 env）。
