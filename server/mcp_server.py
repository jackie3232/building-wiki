"""
BUILDING.WIKI · MCP 工具层（MVP 2.0）
================================================
把 ④⑤ 引擎包成官方 MCP 工具，供 OAK Agent 通过 HTTP 调用。

使用官方 mcp SDK 2.x（mcp==2.2.0）：
  - FastMCP 在 2.x 已更名为 MCPServer（from mcp.server.mcpserver import MCPServer）
  - 服务端 ASGI 由 mcp.streamable_http_app() 产出（Starlette），stateless_http=True

红线（§13.4#1，2026-09-22 收窄）：LLM 不得接触坐标 / 几何量（坐标、朝向、镜像、
由尺寸推坐标的运算）；业务量可在图谱骨架声明，但取值须来自知识中心值域。
因此只暴露：
  - ping                 ：连通性冒烟测试
  - compute_geometry     ：④ 实例图谱 -> 构件清单（连续几何/绝对坐标/米/Y-up）
  - geometry_to_boxes    ：⑤ 构件清单 -> 体素 BOX 清单

自然语言 <-> 实例图谱的推导在 Agent/理解层完成；数字与坐标全在引擎内算。

本模块只定义 MCPServer 实例与工具；ASGI 挂载（/mcp）在 app.py 完成，
以便复用同一份 Starlette 应用同时承载既有 HTTP 路由与 MCP 端点。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from engine.geometry import compute_geometry, geometry_to_boxes

# MCPServer name = agent.yaml 里 mcp_servers[].name（须一致）
mcp = MCPServer(name="building-wiki")


@mcp.tool(name="ping")
def ping() -> str:
    """连通性冒烟测试。返回 "pong" 表示 MCP Server 存活。"""
    return "pong"


@mcp.tool(name="compute_geometry")
def compute_geometry_tool(instance: dict) -> str:
    """④ 几何计算：实例图谱 -> 构件清单。

    Args:
        instance: 自包含实例图谱（数据中心，不含坐标/数字，仅业务语义）。
    Returns:
        JSON 字符串：构件清单，每项形如 {role, center:{x,y,z}, size:{w,h,d}}（米，Y-up）。
        庭院虚空不输出。调用方需 json.loads 解析。
    """
    # 返回 JSON 字符串而非裸 list：mcp 2.x 对裸 list 返回值的序列化会丢字段，
    # 字符串化后由调用方 json.loads，保真且跨客户端兼容。
    #
    # 必须包 ToolError：mcp 2.x 对非 ToolError 异常一律压成
    # `Error executing tool compute_geometry`（tools/base.py:210），
    # 引擎的「图谱缺陷：…」诊断会全部丢失，模型只能看到一句无信息量的报错，
    # 进而误判为服务端故障。包成 ToolError 后原文透传到模型 content。
    try:
        return json.dumps(compute_geometry(instance), ensure_ascii=False)
    except Exception as e:
        raise ToolError("%s: %s" % (type(e).__name__, e)) from e


@mcp.tool(name="geometry_to_boxes")
def geometry_to_boxes_tool(geometry: list[dict]) -> str:
    """⑤ 几何造型：构件清单 -> 体素 BOX 清单（真实多体素化）。

    Args:
        geometry: compute_geometry 的输出（构件清单，list[dict]）。
    Returns:
        JSON 字符串：体素 BOX 清单，每项形如 {x,y,z,w,h,d,role,label,color}。
        调用方需 json.loads 解析。
    """
    # 同 compute_geometry_tool：包 ToolError，避免诊断信息被 SDK 压成
    # `Error executing tool geometry_to_boxes`。
    try:
        return json.dumps(geometry_to_boxes(geometry), ensure_ascii=False)
    except Exception as e:
        raise ToolError("%s: %s" % (type(e).__name__, e)) from e
