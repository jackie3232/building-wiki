"""
BUILDING.WIKI · MCP 工具层（MVP 2.0）
================================================
把 ④⑤ 引擎包成官方 MCP 工具，供 OAK Agent 通过 HTTP 调用。

使用官方 mcp SDK 2.x（mcp==2.2.0）：
  - FastMCP 在 2.x 已更名为 MCPServer（from mcp.server.mcpserver import MCPServer）
  - 服务端 ASGI 由 mcp.streamable_http_app() 产出（Starlette），stateless_http=True

红线（§13.4#1，2026-09-22 收窄）：LLM 不得接触坐标 / 几何量（坐标、朝向、镜像、
由尺寸推坐标的运算）；业务量可在图谱骨架声明，但取值须来自知识中心值域。
因此只暴露两个工具（单入口）：
  - ping                 ：连通性冒烟测试
  - generate_building    ：④⑤ 一体化（by-reference）。入参只传实例图谱引用
                          （cos:<key> 或本地路径），内部读实例 -> ④⑤ ->
                          返回体素 BOX 清单（云存储预签名 URL）。让 OAK Agent 成为整条链路总控。

  实例图谱的**合规校验只在智能侧（装配出口）做一次**（assemble.mjs 的 validateInstanceGraph，
  读知识包）。本服务端不再重复校验——守卫交给 ④ 自带的形状闸 _graph_data
  （入参不是自包含实例图谱即报错，不静默产出）。

  ④ compute_geometry / ⑤ geometry_to_boxes 已收窄为 generate_building 的内部步骤，
  不再单独暴露（2026-09-27 收窄单入口 —— 这两个工具是「前端两步直连」时代的遗留）。

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


@mcp.tool(name="generate_building")
def generate_building_tool(instance_ref: str) -> str:
    """④⑤ 一体化（by-reference）：实例图谱引用 -> 体素 BOX 清单。

    自动化侧的唯一业务入口（单入口）。内部顺序：
    read_instance -> compute_geometry（④）-> geometry_to_boxes（⑤）
    -> 体素写云存储、回传预签名 URL。

    合规校验不在此处：实例图谱的硬闸只在智能侧（装配出口）做一次。本处的守卫
    是 ④ 自带的形状闸 _graph_data —— 入参若非自包含实例图谱即报「图谱缺陷」，
    绝不静默产出。

    入参只传「引用」而非「值」：实例图谱 ~10KB 若走工具入参通道会被 harness
    截断损坏，故 Agent 先把实例写到云存储（cos:<key>），本工具按引用读取。

    Args:
        instance_ref: 实例图谱引用。生产为 cos:<objectKey>
                      （Agent 写入云存储的键，如 cos:instances/<uuid>.json）；
                      本地调试可为磁盘文件路径。解析见 storage.read_instance。
    Returns:
        默认（by-reference，与入参对称）：体素 BOX 清单写入云存储，返回 JSON 字符串：
            {"boxes_ref": "<预签名URL>", "instance_ref": "<入参原样回传>"}
        - boxes_ref：可公网 GET 的预签名 URL，前端/调用方按 URL 直接 fetch 取体素，
          绕开 harness 对大输出（~0.5–1MB）的持久化/截断。
        - instance_ref：把入参的实例图谱引用原样回传（2026-09-29 方案 B 新增），
          使「编辑」链路闭环——前端从结构化工具结果稳定拿到下一次编辑所需的
          instance_ref，无需解析 Agent 自然语言。
        设 BW_BOXES_INLINE=1 时 boxes_ref 改为内联体素 JSON 字符串（本地调试用）。
    """
    # 包 ToolError：保留「图谱缺陷：…」诊断原文透传到模型；
    # 引用解析失败（缺凭据 / 键不存在 / JSON 损坏）也一并透传。
    try:
        instance = read_instance(instance_ref)
        geometry = compute_geometry(instance)
        boxes = geometry_to_boxes(geometry, instance=instance)
        if os.environ.get("BW_BOXES_INLINE") == "1":
            boxes_ref = boxes          # 本地调试：直接内联数组（前端按数组处理）
        else:
            # 出参走引用：写云存储，只回传可取路径（预签名 URL），与入参 cos: 引用对称。
            key = new_object_key("oak-workspaces/boxes")
            write_json(key, boxes)
            boxes_ref = presign_url(key, expires=3600)
        # 方案 B：instance_ref 原样回传，支撑「实例图谱为真相源 + 前端持有回灌 + 每轮重算」。
        return json.dumps({"boxes_ref": boxes_ref, "instance_ref": instance_ref},
                          ensure_ascii=False)
    except Exception as e:
        raise ToolError("%s: %s" % (type(e).__name__, e)) from e
