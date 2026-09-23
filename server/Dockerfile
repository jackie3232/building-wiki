# ===========================================================================
# 工程数据发动机 · MVP —— CloudRun 容器（纯 Python 体素版）
#
#  取代旧版「Stage1 GCC/CMake 编译 OCCT/CGAL 引擎 + Stage2 复制 voxelcli」
#  两阶段构建。MVP 选定 ⑤ 走 Box 体素提速版（Python 重写），不再依赖
#  C++/OCCT/CGAL，故整条链路为纯 Python 标准库，零编译、零原生依赖。
#
#  管线（2.0）：Agent（LLM 出骨架 → skill 装配实例图谱）
#            → MCP compute_geometry(④) → geometry_to_boxes(⑤)
#            → 客户端渲染（前端独立部署，不在本容器内）
#
#  路径约定（与 engine/geometry.py 的 BASE 解析一致）：
#    app.py              → /app/app.py         (纯 MCP 宿主)
#    mcp_server.py       → /app/mcp_server.py  (ping / compute_geometry / geometry_to_boxes)
#    engine/             → /app/engine/        (④⑤ 计算引擎，纯 Python)
#    knowledge/          → /app/knowledge/     (dict/type/rules；⑤ label 与 ① 基线用)
#    data/               → /app/data/          (instances 实例工程文件)
# ===========================================================================

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=80

WORKDIR /app

# MVP 2.0：引入官方 mcp SDK（ASGI），需装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY mcp_server.py .
COPY storage.py .
COPY engine ./engine
COPY knowledge ./knowledge
COPY data ./data

EXPOSE 80
CMD ["python", "app.py"]
