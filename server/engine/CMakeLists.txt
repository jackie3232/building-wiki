cmake_minimum_required(VERSION 3.16)
project(voxelcli CXX)

# ---------------------------------------------------------------------------
# Linux 原生建模引擎（与 Windows 侧 D:\sourcecodes\n1\voxelcli\main.exe 同源）
#
# 源码来自 D:\sourcecodes\n1，经 sync_from_n1.sh 同步到本目录（单一事实源）。
# 依赖：OCCT 7.6 / CGAL 5.x / Boost / rapidjson（Debian bookworm 的 apt 包 + vendored rapidjson）
# ---------------------------------------------------------------------------

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# OCCT：Debian 的 libocct-foundation-dev 提供
#   /usr/lib/<triplet>/cmake/opencascade/OpenCASCADEConfig.cmake
# CMake 默认搜索路径即可命中，无需设置 OpenCASCADE_DIR。
find_package(OpenCASCADE REQUIRED)

# rapidjson：vendored（third_party/rapidjson，与 n1 工程 rapidjson-1.1.0 逐字节同源）。
# 优先本地副本；不存在时退回系统包（rapidjson-dev）。
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/third_party/rapidjson/document.h)
  set(RAPIDJSON_INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
else()
  find_path(RAPIDJSON_INCLUDE_DIR rapidjson/document.h REQUIRED)
endif()

add_executable(voxelcli
  cli/main.cpp
  modelling/body.cpp
  modelling/cgalUtilities.cpp
  modelling/geometry.cpp
  modelling/IdCreator.cpp
  modelling/LayoutNet.cpp
  modelling/modelling.cpp
  modelling/MyString.cpp
  modelling/MyUtilities.cpp
  modelling/occUtilities.cpp
  modelling/RandomColor.cpp
  modelling/pch.cpp
  modelling/site.cpp
  modelling/TopoDS_Shape_Map.cpp
  modelling/topology.cpp
)

target_include_directories(voxelcli PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/inc/modelling
  ${CMAKE_CURRENT_SOURCE_DIR}/modelling
  ${RAPIDJSON_INCLUDE_DIR}
  ${OpenCASCADE_INCLUDE_DIR}
)

# --- OCCT 工具包 -------------------------------------------------------------
# 不依赖 OpenCASCADEConfig.cmake 里变量的具体语义：显式按名称解析 lib<TK>.so
# （Debian 的 libocct-*-dev 包在 /usr/lib/<triplet>/ 下提供这些 .so 链接符号）。
set(OCCT_TOOLKITS
  TKernel TKMath
  TKG2d TKG3d TKGeomBase TKBRep
  TKGeomAlgo TKTopAlgo TKPrim TKBO TKBool TKHLR TKShHealing
  TKFillet TKOffset TKFeat TKXMesh TKMesh
  TKSTL TKIGES TKSTEP TKSTEPBase TKSTEPAttr TKSTEP209 TKXSBase
  TKCDF TKLCAF TKCAF TKXCAF TKVCAF
)
set(OCCT_LIBS "")
foreach(tk IN LISTS OCCT_TOOLKITS)
  find_library(OCCT_${tk}_LIBRARY NAMES ${tk})
  if(OCCT_${tk}_LIBRARY)
    list(APPEND OCCT_LIBS ${OCCT_${tk}_LIBRARY})
  else()
    message(WARNING "[engine] 未解析到 OCCT 工具包 ${tk}（若链接报未定义符号，请检查 libocct-*-dev 安装）")
  endif()
endforeach()

# 兜底：逐个解析全空时，退回 find_package 提供的整包列表
if(NOT OCCT_LIBS)
  set(OCCT_LIBS ${OpenCASCADE_LIBRARIES})
  message(STATUS "[engine] 退回 OpenCASCADE_LIBRARIES（${OpenCASCADE_LIBRARIES}）")
endif()
if(NOT OCCT_LIBS)
  message(FATAL_ERROR "[engine] 未解析到任何 OCCT 库，请确认已安装 libocct-foundation-dev 等 -dev 包")
endif()

# CGAL 为纯头文件使用（Simple_cartesian / Arrangement_2 / Boolean_set_operations_2），GMP/MPFR 供其内核解析
find_library(GMP_LIB gmp)
find_library(MPFR_LIB mpfr)

# --as-needed：避免把未实际引用的 OCCT 库写进 DT_NEEDED（运行时镜像只装必要运行库）
target_link_options(voxelcli PRIVATE -Wl,--as-needed)

target_link_libraries(voxelcli PRIVATE ${OCCT_LIBS})
if(GMP_LIB)
  target_link_libraries(voxelcli PRIVATE ${GMP_LIB})
endif()
if(MPFR_LIB)
  target_link_libraries(voxelcli PRIVATE ${MPFR_LIB})
endif()

target_compile_options(voxelcli PRIVATE -O2)

# 引擎输出的中文名与前端 JSON 均按 UTF-8 处理（源码已统一为 UTF-8+BOM）
