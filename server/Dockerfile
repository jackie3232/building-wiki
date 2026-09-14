# ===========================================================================
# 工程数据发动机 · MVP —— CloudRun 容器（纯 Python 体素版）
#
#  取代旧版「Stage1 GCC/CMake 编译 OCCT/CGAL 引擎 + Stage2 复制 voxelcli」
#  两阶段构建。MVP 选定 ⑤ 走 Box 体素提速版（Python 重写），不再依赖
#  C++/OCCT/CGAL，故整条链路为纯 Python 标准库，零编译、零原生依赖。
#
#  管线：NL → ①(text_to_instance) → instance(工程文件)
#            → ④(geometry 纯几何) → ⑤(box 体素) → ⑥(前端 Three.js 渲染)
#
#  路径约定（与 engine/geometry.py 的 BASE 解析一致）：
#    app.py              → /app/app.py
#    engine/             → /app/engine/        (④⑤ 计算引擎，纯 Python)
#    knowledge/          → /app/knowledge/     (type.json + rules，① 合成用)
#    data/               → /app/data/          (instances 实例工程文件)
#    static/             → /app/static/        (前端页面 + Three.js)
# ===========================================================================

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=80

WORKDIR /app

# 零依赖：仅 Python 标准库 http.server，无需 pip 安装任何包
COPY app.py .
COPY engine ./engine
COPY knowledge ./knowledge
COPY data ./data
COPY static ./static

EXPOSE 80
CMD ["python", "app.py"]
