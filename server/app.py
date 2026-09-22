"""
BUILDING.WIKI · MVP 2.0 服务（Starlette ASGI）
================================================
本容器 = **纯 MCP 引擎出口**（2.0 唯一职责）。

  /mcp  -> 官方 mcp SDK Streamable HTTP（stateless）
            工具：ping / compute_geometry / geometry_to_boxes

为什么只剩 /mcp（2026-09-22 决策：全线 2.0，1.0 下线）
------------------------------------------------------------
1.0 时代本应用还承载过四条 HTTP 路由：`/`（Three.js 查看器）、`/static/*`、
`/api/dict`、`/api/command`（服务端 ① 理解层 LLM + ④⑤ + tour）。2.0 把这些
职责一分为二后，它们全部失去存在理由：

  - ① 理解层 → 归 OAK Agent（LLM 在 Agent 侧，产出骨架）
  - ④⑤      → 归本容器，但只经 MCP 暴露给 Agent（不再对浏览器直供）
  - ⑥ 渲染    → 归独立前端（新起，不再是本容器的 `/` + `/static`）

故摘掉全部 1.0 HTTP 路由，容器只留 /mcp。
1.0 的实现内容已一并清除（2026-09-22 决策：1.0 内容不再保留）——
`static/`（查看器与图谱视图）、`engine/understanding.py`（服务端 ① 理解层）、
`geometry.text_to_instance`（1.0 的 NL 入口）均已删除。
`mcp_server.py` 只依赖 `engine.geometry`，与理解层无耦合，故该切割不波及 /mcp。

约束与坑（实测）
------------------------------------------------------------
- 官方 mcp SDK 2.x：直接 Mount `streamable_http_app()` 的子 Starlette 应用时，其
  lifespan（session_manager.run）不会被父应用 Mount 触发（Starlette 的 Mount 不跑
  子应用 lifespan），会报 "Task group is not initialized"。故自建
  StreamableHTTPSessionManager，由父应用 lifespan 统一调度 run()。
- stateless=True：无持久长连接，规避 Cloud Run 超时顾虑。
- json_response=True：单条 JSON 响应（非 SSE 流）。实测 SSE 流在较大响应体
  （geometry_to_boxes 输出数千体素 BOX、数百 KB）时会提前断流
  （"SSE stream ended without a response"）；Json 模式规避流式分片。
- 保留 CORS（allow_origins=["*"]）：浏览器侧客户端（如 MCP Inspector / 新前端）
  直连 /mcp 时需要；MCP 本身不限制来源，此处不构成额外暴露面。
"""
import os
import sys
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server import mcp  # noqa: E402

session_manager = StreamableHTTPSessionManager(
    app=mcp._lowlevel_server,
    stateless=True,
    json_response=True,
)


@asynccontextmanager
async def lifespan(app):
    async with session_manager.run():
        yield


routes = [
    Mount("/mcp", app=session_manager.asgi_app),
]

app = Starlette(
    routes=routes,
    lifespan=lifespan,
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"],
                           allow_methods=["*"], allow_headers=["*"])],
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[BUILDING.WIKI] MVP 2.0 MCP-only server on http://0.0.0.0:{port} (mcp at /mcp)")
    # proxy_headers：信任上游代理转发的 X-Forwarded-Proto/Host。Cloud Run 处在
    # TLS 终止代理之后；若不信任转发头，Starlette 对 "/mcp" 的补斜杠 307 会指向
    # http://，MCP 客户端因「HTTPS -> HTTP 降级」拒绝跟随。开启后重定向仍为 https。
    uvicorn.run(app, host="0.0.0.0", port=port,
                proxy_headers=True, forwarded_allow_ips="*")
