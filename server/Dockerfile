# ===========================================================================
# 工程数据发动机 · MVP —— CloudRun 容器（两阶段构建）
#
#   Stage 1  engine-builder  Debian bookworm 里用 GCC/CMake 编译 n1 建模引擎
#                            （server/engine/ ← 与 Windows 侧 D:\sourcecodes\n1 同源），
#                            产出 Linux 原生可执行 voxelcli，并当场跑一次冒烟自检。
#   Stage 2  runtime         python:3.11-slim-bookworm + OCCT 运行库 + 引擎二进制，
#                            单服务 Flask 托管前端静态页与 /api/command。
#
# 为何两阶段都锁 bookworm（Debian 12）：
#   OCCT 在 Debian 12 = 7.6.3（包名 libocct-*-7.6），在 Debian 13 trixie = 7.8.x；
#   构建期与运行期必须同 ABI。且 `python:3.11-slim` 浮动标签现已指向 trixie，
#   故显式锁定 `-bookworm` 后缀，避免上游换代导致镜像静默漂移。
#
# 编码：n1 源码在 Linux 侧已统一为 UTF-8（含 BOM），与 JSON 输入同编码，
#       引擎内的中文空间名匹配（庭院/阳台等）无需转码。详见 engine/README.md。
# ===========================================================================

# --------------------------- Stage 1: 引擎构建 -----------------------------
FROM debian:bookworm-slim AS engine-builder

# build-essential + cmake 编译；libocct-*-dev 提供 OCCT 头文件与 lib<TK>.so 链接符号；
# libcgal-dev（头文件库，自动带入 boost/gmp/mpfr/zlib）；rapidjson 为 vendored，无需 apt。
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libocct-foundation-dev \
        libocct-modeling-data-dev \
        libocct-modeling-algorithms-dev \
        libocct-data-exchange-dev \
        libocct-ocaf-dev \
        libcgal-dev \
        libgmp-dev \
        libmpfr-dev \
        zlib1g-dev; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src
# 引擎镜像树（源码 + CMakeLists.txt + third_party/rapidjson）
COPY engine ./engine

RUN set -eux; \
    cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release; \
    cmake --build engine/build --target voxelcli -- -j"$(nproc)"; \
    test -x engine/build/voxelcli

# 冒烟自检：用随包图谱真跑一遍（图谱 → STL + stats JSON），
# 把 OCCT/CGAL/空间名匹配/STL 导出的问题在【构建期】暴露，而不是等上线后才发现。
# 注：引擎自 2026-09-11 起不再输出 boxes（接口只交付 STL），产物里已无中文标签；
#     改以「非零几何」作判据——walls/doors 任一为 0 即说明建墙或连接名匹配断了。
COPY data/case_6.json /smoke/case_6.json
RUN set -eux; \
    echo "--- ldd ---"; ldd engine/build/voxelcli; \
    if ldd engine/build/voxelcli | grep -q "not found"; then \
        echo "[FATAL] 引擎存在未解析的动态库依赖" >&2; exit 1; \
    fi; \
    engine/build/voxelcli /smoke/case_6.json /smoke/out.json; \
    test -s /smoke/out.json; \
    test -s /smoke/out.stl; \
    echo "--- 产物 ---"; \
    wc -c /smoke/out.json /smoke/out.stl; \
    cat /smoke/out.json; \
    grep -q '"stl"' /smoke/out.json; \
    if grep -q '"walls":0' /smoke/out.json; then \
        echo "[FATAL] walls=0：createWalls 未生成墙体" >&2; exit 1; \
    fi; \
    if grep -q '"doors":0' /smoke/out.json; then \
        echo "[FATAL] doors=0：门/窗连接名匹配失败（编码或图谱问题）" >&2; exit 1; \
    fi; \
    echo "[OK] 引擎冒烟通过：STL 已产出，walls/doors 非零"

# --------------------------- Stage 2: 运行时 -------------------------------
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=80

WORKDIR /app

# OCCT 运行库：引擎动态链接依赖，与构建阶段同为 7.6（ABI 一致）。
# 只装 foundation/modeling/data-exchange/ocaf —— 可视化（TKV3d/TKOpenGl）用不到，
# 构建期已用 -Wl,--as-needed 确保未引用库不会写进 DT_NEEDED。
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libocct-foundation-7.6 \
        libocct-modeling-data-7.6 \
        libocct-modeling-algorithms-7.6 \
        libocct-data-exchange-7.6 \
        libocct-ocaf-7.6 \
        libgmp10 \
        libmpfr6; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY static ./static
# 兜底预生成产物（shapes_case6.json/.stl）：引擎缺失时仍可演示；
# 引擎就位后每次请求都由引擎实时覆写，仅为最后防线。
COPY data ./data

# Linux 原生建模引擎（app.py 以 os.path.exists(BASE_DIR/bin/voxelcli) 判定可用）
COPY --from=engine-builder /src/engine/build/voxelcli ./bin/voxelcli

EXPOSE 80
CMD ["python", "app.py"]
