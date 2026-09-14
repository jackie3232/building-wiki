# 几何计算引擎（④）I/O 契约

> 定位：纯几何计算（Geometry），不含图形（Graphic）。输入是实例工程文件，输出是构件列表。
> 约定：建筑/工程域称「构件」，工业域称 Part/零件；二者在几何引擎里是同一类输出原语（几何实体）。

## 输入契约 Input
- **来源**：整个 `instance` 工程文件（`data` 块 + `appliedRules` 块）—— 自包含、零外部依赖。
- **不消费**：外部知识中心文件 `dict.json` / `rules.json`。`dict` 词表属 ① 语义理解，④ 不碰。
- **从 `data` 取**：拓扑 + 本次实例具体值 ——
  - `courtyards[]` 的 `sequence`（沿中轴南北排布顺序）
  - 各院 `enclosure` 四向：`north/south/east/west` 各自的 `role` + `miankuo`(面阔间数) + `jinshen`(进深间数)
  - `northGate` / `southGate`（垂花门位置）
  - `center`（庭院）、`peripheral`（游廊/影壁）
  - `jin`（进数）
- **从 `appliedRules` 取（rules 驱动，不硬编码）**：`norms` 里的换算标准 ——
  - `MODUS`（间→米换算系数）
  - `ratio`（明:次:梢 = 10:8:6，为微观细分铺路）

## 输出契约 Output
- **构件列表**（list of components / parts），每个是一个**连续几何实体**。
- **每个构件** = `{role, center:{x,y,z}, size:{w,h,d}, ...}`
  - 绝对坐标、Y-up、单位米
  - **无 color / 无 label**（属 ⑤ 造型层）
- **构件 ≠ Box**：构件 : Box = 图像 : 像素。一个构件由 ⑤ 体素化后拆成**多个** box，不是一个构件一个 box。
- **不输出「空间」**：空间是构件围合出的虚空（概念层），不进 ④ 输出。
  - 庭院 = 开敞虚空 → 不输出为实心体（⑤ 可用地坪/留空表现）
  - 游廊 / 影壁 = 实体构件 → 要输出

## 四合院构件集（MVP 粗粒度：1 房间 = 1 构件块）
正房、厢房×2（每院东/西）、倒座房、后罩房、垂花门（按 gate 数）、游廊、影壁。
> 注：微观细分（房间拆成 墙/柱/梁/板/门洞 多个构件）为后续粒度，不在 MVP 粗粒度范围。

## 与 ⑤ 的边界
- ④ = 连续几何（构件）；⑤ = 体素化（构件 → box 像素网格）+ 上色 + 标签，是造型策略选择器（Box / B-rep）。
- ④ **不预设 box**。

## 数据流
```
NL → ① LLM理解 → instance(工程文件: data + appliedRules)
     → ④ compute_geometry → 构件列表(连续几何)
     → ⑤ 体素化 → box 像素网格
     → ⑥ 渲染
```
