# engine/ —— Linux 原生建模引擎（构建输入）

本目录是 **n1 引擎工程的镜像**，仅供 Docker 构建期在 Linux 上编译出原生引擎可执行文件。

## 为什么需要它

CloudRun 的构建上下文是 `server/`，无法访问 `D:\sourcecodes\n1`。
而 n1 引擎（`modelling` + `voxelcli/main.cpp`）是同一份源码，
Windows 侧用 MSVC 编成 `main.exe`，Linux 侧用 g++ 编成 `bin/voxelcli`。
本目录承载后者所需的源码子集。

## 单一事实源

**权威源码在 `D:\sourcecodes\n1`**。本目录由脚本同步而来，不要在此直接改代码：

```bash
bash server/engine/sync_from_n1.sh          # 默认源 /d/sourcecodes/n1
```

改动引擎源码的正确顺序：**改 n1 → 跑 sync 脚本 → 重新部署**。

## 编码约定（重要）

n1 源码原本是 **GBK**（含中文注释与「庭院/阳台」等空间名字面量）。现已统一为
**UTF-8 + BOM**，两侧编译器表现如下：

| 平台 | 编译器 | 源文件解码 | 窄字面量执行字符集 | 结果 |
|---|---|---|---|---|
| Windows | MSVC（**无** `/utf-8`） | BOM → UTF-8 | ANSI(GBK) | 字面量字节 = GBK（与原行为**逐字节一致**） |
| Linux | g++（默认） | UTF-8 | UTF-8 | 字面量字节 = UTF-8 |

因此 `cli/main.cpp` 里的 `u8ToGbk()/gbkToU8()` 在 Windows 上做 UTF-8→GBK 转换，
在 Linux 上**恒等直通**（源码见 `#if defined(_WIN32)` 分支）。
两条路径最终语义一致：**送入引擎的空间名与引擎字面量同编码**。

> 历史教训：GBK 源码曾导致「庭院」被判成室内 → 屋顶盖满全院成大盒子。
> 统一 UTF-8 后该类问题从源头消除。

## 目录

```
engine/
  CMakeLists.txt        # 构建 voxelcli（链接 OCCT / CGAL / Boost）
  sync_from_n1.sh       # 从 n1 同步源码（含 vendored rapidjson）
  cli/main.cpp          # ← n1/voxelcli/main.cpp
  modelling/            # ← n1/modelling/*（不含 dllmain.cpp）
  inc/modelling/        # ← n1/inc/modelling/*
  third_party/rapidjson # ← n1/rapidjson-1.1.0/rapidjson（头文件库，逐字节同源）
```

## 构建（Docker 构建期自动执行）

`../Dockerfile` 的 `engine-builder` 阶段：

```bash
cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build --target voxelcli -j"$(nproc)"
```

依赖（Debian bookworm apt）：`build-essential cmake libocct-{foundation,modeling-data,modeling-algorithms,data-exchange,ocaf}-dev libcgal-dev`。
rapidjson 用本目录 vendored 副本，**不装 apt 包**。

**基础镜像必须锁 `bookworm`（Debian 12）**：OCCT 在 Debian 12 是 7.6.3（`libocct-*-7.6`），
在 Debian 13 trixie 是 7.8.x；构建期与运行期要同 ABI。注意 `python:3.11-slim` 浮动标签
已指向 trixie，故 Dockerfile 显式用 `python:3.11-slim-bookworm`。

构建阶段会跑一次**冒烟自检**（拿 `data/case_6.json` 真跑一遍），校验四件事：
产物 JSON 里 `stl` 字段存在、STL 文件非空、`stats.walls` 非 0、`stats.doors` 非 0。
构建期即暴露 OCCT/CGAL/空间名匹配问题，不必等上线。

> 引擎自 2026-09-11 起**不再输出 boxes**（对外只交付 STL），故产物 JSON 里没有中文标签，
> 冒烟自检改以「非零几何」作判据。`main.cpp` 中已无任何非 ASCII 字面量（中文只在注释里）。

