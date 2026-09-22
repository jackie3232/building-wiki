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
   ├─ assemble.mjs（确定性查表装配）：骨架 → 自包含实例图谱
   │        ↓
   └─ 你把 instance.json 打印出来（cat）—— 到这一步你就收工
            ↓
      前端接手：直连 MCP 跑 compute_geometry（图谱→构件）→ geometry_to_boxes（构件→体素）
```

**你负责智能化（理解 + 出骨架）与装配调用；④⑤ 全由前端直连 MCP 做，不经你手。**

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

## 怎么出模型

装配出实例图谱后，**把 `instance.json` 的完整内容打印到输出里**：

```bash
cat instance.json
```

打印完 —— **你的任务就到此结束**。

**一个 MCP 工具都不要调。** ④ 几何计算、⑤ 体素化全部由**前端直连 MCP 执行**：
它们的入参/输出是十几 KB ~ 400KB 的坐标数据，既撑不过你的工具调用通道（实测会被破坏成
非法形态、必然失败重试），也是你必须回避的坐标。你只要把实例图谱原样交出即可。

**出错时不要自己编几何/坐标**——那是踩红线。把工具的原始报错读回来，
检查是不是骨架不合法（role 不在词表 / jin 与 courtyards 数量不符），改骨架重试。
