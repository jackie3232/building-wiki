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
  - generate_building    ：④⑤ 一体化（by-reference）。入参只传实例图谱引用
                          （cos:<key> 或本地路径），内部读实例 -> 跑 ④⑤ ->
                          返回体素 BOX 清单 JSON。让 OAK Agent 成为整条链路总控。

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
from storage import read_instance, write_json, presign_url, new_object_key

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


@mcp.tool(name="generate_building")
def generate_building_tool(instance_ref: str) -> str:
    """④⑤ 一体化（by-reference）：实例图谱引用 -> 体素 BOX 清单。

    把原先前端分两步直连的 compute_geometry + geometry_to_boxes 合并为
    Agent 侧的一次工具调用，使 OAK Agent 成为整条链路的总控
    （架构决策 2026-09-22：全 Agent 形态，自动化段打包为单个 MCP 调用）。

    入参只传「引用」而非「值」：实例图谱 ~10KB 若走工具入参通道会被 harness
    截断损坏，故 Agent 先把实例写到云存储（cos:<key>），本工具按引用读取。

    Args:
        instance_ref: 实例图谱引用。生产为 cos:<objectKey>
                      （Agent 写入云存储的键，如 cos:instances/<uuid>.json）；
                      本地调试可为磁盘文件路径。解析见 storage.read_instance。
    Returns:
        默认（by-reference，与入参对称）：体素 BOX 清单写入云存储，返回一个
        可公网 GET 的预签名 URL 字符串。前端/调用方按 URL 直接 fetch 取体素，
        绕开 harness 对大输出（~0.5–1MB）的持久化/截断。
        设 BW_BOXES_INLINE=1 时改为内联体素 JSON 字符串（本地调试用）。
    """
    # 与另两个工具一致：包 ToolError，保留「图谱缺陷：…」诊断原文透传到模型；
    # 引用解析失败（缺凭据 / 键不存在 / JSON 损坏）也一并透传。
    try:
        instance = read_instance(instance_ref)
        geometry = compute_geometry(instance)
        boxes = geometry_to_boxes(geometry)
        if os.environ.get("BW_BOXES_INLINE") == "1":
            return json.dumps(boxes, ensure_ascii=False)
        # 出参走引用：写云存储，只回传可取路径（预签名 URL），与入参 cos: 引用对称。
        key = new_object_key("oak-workspaces/boxes")
        write_json(key, boxes)
        return presign_url(key, expires=3600)
    except Exception as e:
        raise ToolError("%s: %s" % (type(e).__name__, e)) from e
