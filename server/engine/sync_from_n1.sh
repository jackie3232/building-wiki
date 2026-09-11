#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 从 n1 引擎工程同步「Linux 构建所需的源码子集」到本目录（server/engine/）。
#
# 单一事实源：D:\sourcecodes\n1（Windows / MSVC 工程，n1 侧仍是权威）。
# 本目录是它的镜像，仅用于 Docker 构建 Linux 原生引擎（见 ../Dockerfile）。
#
# 改动引擎源码时：先改 n1，再执行本脚本同步，然后重新部署。
#   bash server/engine/sync_from_n1.sh [N1_DIR]
# N1_DIR 默认 /d/sourcecodes/n1
# ---------------------------------------------------------------------------
set -euo pipefail

N1="${1:-/d/sourcecodes/n1}"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$N1/modelling" ]; then
  echo "[ERR] 未找到 n1 工程：$N1" >&2
  exit 1
fi

# modelling 源文件（排除 dllmain.cpp：Windows 专属，Linux 为静态库无需它）
MODELLING_FILES=(
  body.cpp
  cgalUtilities.cpp cgalUtilities.h
  geometry.cpp
  IdCreator.cpp IdCreator.h
  LayoutNet.cpp
  modelling.cpp
  MyCGAL.hpp MyOCC.hpp
  MyString.cpp
  MyUtilities.cpp MyUtilities.h
  occUtilities.cpp occUtilities.h
  RandomColor.cpp
  pch.cpp pch.h framework.h
  site.cpp
  TopoDS_Shape_Map.cpp TopoDS_Shape_Map.h
  topology.cpp
)
# 公共头（inc/modelling）
INC_FILES=(
  LayoutNet.h RandomColor.h body.h dll.h geometry.h inc.h
  modelling.h mystring.h site.h topology.h
)

mkdir -p "$DST/modelling" "$DST/inc/modelling" "$DST/cli"

copied=0
for f in "${MODELLING_FILES[@]}"; do
  [ -f "$N1/modelling/$f" ] || { echo "[SKIP] 不存在（可能已改名）：modelling/$f" >&2; continue; }
  cp -p "$N1/modelling/$f" "$DST/modelling/$f"
  copied=$((copied+1))
done
for f in "${INC_FILES[@]}"; do
  [ -f "$N1/inc/modelling/$f" ] || { echo "[ERR] 缺失公共头：inc/modelling/$f" >&2; exit 1; }
  cp -p "$N1/inc/modelling/$f" "$DST/inc/modelling/$f"
  copied=$((copied+1))
done
cp -p "$N1/voxelcli/main.cpp" "$DST/cli/main.cpp"
copied=$((copied+1))

# rapidjson：随 n1 工程分发的 1.1.0 头文件（仅头文件库）。
# 一并 vendored 进镜像树，使 Linux 构建所用 [[rapidjson/document.h]] 与 Windows 侧逐字节同源，
# 同时免去构建期 apt 安装 rapidjson-dev（消除版本漂移与网络依赖）。
mkdir -p "$DST/third_party/rapidjson"
if [ -d "$N1/rapidjson-1.1.0/rapidjson" ]; then
  cp -rp "$N1/rapidjson-1.1.0/rapidjson/." "$DST/third_party/rapidjson/"
  copied=$((copied+1))
else
  echo "[ERR] 缺失 rapidjson：$N1/rapidjson-1.1.0/rapidjson" >&2
  exit 1
fi

echo "[OK] 已同步 $copied 个条目 → $DST"
echo "     （Windows 侧产物 main.exe 不受影响；重新部署即可让 Linux 侧编出新引擎）"
