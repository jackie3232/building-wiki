# OCCT 导出格式调研（实证）

> 目的：确认 OCCT 能否把"真开洞"模型导出为通用格式，供 building-wiki 的 Three.js 查看器使用。

## 结论

1. **OCCT 支持多种通用导出格式**，已实跑验证：BREP / STEP / STL / VRML 全部成功。
2. **"真开洞"模型可导出**：用 `BRepAlgoAPI_Cut` 布尔减（实测面数 6→10），导出的几何里洞是真拓扑/真三角网格，不是染色近似。
3. **之前的编译失败不是 .lxx 不存在**，而是 `n1/occ/inc` 被裁剪（仅 93 个 `.lxx`）。完整版在 `n1Package/occt/occt_vc14-64/inc`（418 `.lxx` + 7307 `.hxx`）。
4. **Three.js 桥接用 STL**：本构建缺 `TKDEGLTF`/`TKDEOBJ`，glTF/OBJ 不可用；但 STL 有原生 `STLLoader`，足够。

## 实证产物

- `export_test.cpp`：建方块→布尔减洞→导出 BREP/STEP/STL/VRML。
- `out.brep` / `out.step` / `out.stl` / `out.wrl`：四个格式的实际导出文件。

运行结果：
```
faces before cut = 6
faces after  cut = 10  (more => real opening)
BREP  written
STEP  written (status=1=OK)
STL   written
VRML  written
ALL EXPORTS OK
```

## 落地到 building-wiki 的步骤

1. 建模编译的 INCLUDE 改为完整版 `n1Package/occt/occt_vc14-64/inc`（或把缺失 `.lxx` 合并回 `n1/occ/inc`）。
2. 在 `modelling` 对墙执行 `BRepAlgoAPI_Cut`（减去门/窗体积盒子）实现真开洞。
3. 导出 STL，Three.js `STLLoader` 直接渲染。

## 本地不可用格式

- glTF 2.0、OBJ：需 `TKDEGLTF`/`TKDEOBJ` + `RWGltf`/`RWObj`，本构建无对应 DLL。
- 若未来需要 glTF（Three.js 最理想格式），需补齐这两套 toolkit。
