# building.wiki · 图谱驱动体素楼栋 — 建模引擎实时接入总览

## 链路（已落地 · 实时调用）
```
case_6.json（n1 空间图谱，禁坐标）
   └─ server/app.py 收到 build 请求时，实时 subprocess 调用：
        n1/voxelcli/main.exe <case_6.json> <shapes_case6.json>
           ├─ Site/Building/Storey → refreshLayoutNet → createWalls()  ← 建模引擎生成真实墙/板几何
           └─ 抽轴对齐 box：墙=LinearWall::axis()，板=Space::footprint()
                └─ server/data/shapes_case6.json（每次请求现场重新生成）
                     └─ server/app.py 读回并原样 return（无 Python 几何推导）
                          └─ 前端 spawnBoxesFromList → Three.js 体素样式渲染
```
**关键变化（相对旧版）**：不再「离线生成、serve 静态产物」。改为**服务端在每次 build 请求时实时调建模引擎**；若 `main.cpp` 比 `main.exe` 新（或 exe 缺失），先用 MSVC 重新编译再用 —— 即「需要什么编译就重新编译」。

## 关键文件
- `n1/voxelcli/main.cpp` — 读图谱、调建模引擎、生成 shapes（多 storey 循环，楼层标高 `floorIdx*storeyH`）
- `n1/voxelcli/main.exe` — 由 `main.cpp` 编译产出（OCCT 原生，依赖 `modelling.dll`/`TK*.dll`/UCRT 转发 DLL，均已拷至同目录）
- `building.wiki/server/app.py` — `/api/command`：`清空`类→`clear`；其余→实时跑 `main.exe` 生成并返回 box 清单；含重编译判定 + 调用日志
- `building.wiki/server/static/js/main.js` — `spawnBoxesFromList(data.boxes, data.scale)` 消费 `{x,y,z,sx,sy,sz,color,floor}` 渲染

## 实时接入实现要点（app.py）
- `_needs_rebuild()`：比较 `main.cpp` 与 `main.exe` 的 mtime。
- `_compile_main()`：设 `INCLUDE`/`LIB`（含 VC 标准库 + WinSDK + n1 路径）后手动 `cl` 编译；**字节捕获**输出（`text=True` 会因建模引擎非 UTF-8 字节炸），失败抛错。
- `_run_modelling(graph, out)`：需要时先重编译→再 `subprocess` 拉 `main.exe`（`cwd=voxelcli`，PATH 含 bin 与 voxelcli 以解析 DLL）→读回产物。重编失败但旧 exe 可用时降级运行并记日志。
- 每次 build 写一行 `data/modelling_run.log`：{ts, event, recompiled, boxes, walls, slabs, doors, ms}，作为实时调用证据。

## 验证（本轮）
- 单元测试：live run `recompiled=False, boxes=34`；强制 `main.cpp` 比 `exe` 新后 `recompiled=True`（cl 实际重编成功，产物仍为 34 box）。
- HTTP 集成（本地 :5099）：`POST /api/command {"text":"生成四合院"}` → 返回 34 box（27 墙 + 7 板 + 1 门），`realtime:true`；`清空`→`clear`。
- 当前户型（case_6.json = 一进四合院·东厢房开门问题）：单 storey、7 空间（庭院/正房/倒座房/东厢房/西厢房/大门/厕所），1 条连接 东厢房↔庭院 door。

## 已知限制
- 建模引擎对无界「室外空间」伪空间的 `addConnection` 返回 FAIL → 外墙门/窗未着色（interior 门已着色红）。
- OCCT 裁剪版缺 `.lxx` 无法导出带洞真实网格；当前用轴对齐 box 近似墙/板（已是 modelling 真实几何，非 Python 重造）。
- **部署约束**：modelling 是 Windows/MSVC/OCCT 原生库，实时链路依赖本机（Windows）可直接 `subprocess` 拉 `main.exe`。若部署到非 Windows 运行时（如 Linux cloudrun），无法加载该 DLL —— 需把「生成 shapes」前置为构建期步骤，或把建模做成独立 Windows 服务后由本服务调用。
