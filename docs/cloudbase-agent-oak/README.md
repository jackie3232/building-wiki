# CloudBase AI Agent + OAK + MCP 官方文档本地存档

> 存档时间：2026-09-21
> 用途：MVP 2.0（CloudBase 原生 Agent 架构重构）的权威依据。
> 来源：docs.cloudbase.net/ai 下的官方文档（introduce / agent / agent-development/frameworks/oak / agent/knowledgebase 等），以及 OAK SDK 实测。

---

## 0. 结论先行（最关键，先读这段）

我们走的是 **OAK（OpenAgentKernel，`@cloudbase/open-agent-kernel`）官方控制台模板**这条路（Route B），不是 LangChain/LangGraph/CrewAI 那条「框架接入」路（Route A）。

- Route A（框架接入）：用 `@cloudbase/agent-adapter-*` + `createAgentServer`，走 **AG-UI** 协议。
- **Route B（我们的，OAK 控制台模板）**：用 OAK SDK，走 **ACP** 协议，端点以 `/acp` 结尾。自带会话持久化、MCP 工具接入、HITL。
- 两条都是官方路线，**不需要改框架**。我们把 ④⑤ 引擎包成 **HTTP MCP Server**，在 Agent 的 `agent.yaml` 里声明为 `mcp_servers`，OAK 会自动把工具挂载进 Agent。

实测确认：Agent 函数 `agt-building-8gp5in9y2e59d69c` 的 MCP 端点路径为 `/acp`，Agent 通过 ACP 调用我们声明在 `agent.yaml` 里的 `mcp_servers`。

---

## 1. agent.yaml 权威 Schema（来自 /ai/agent/knowledgebase）

```yaml
# 三个字段是必须的
name: oma                      # Agent 名
model: hy3                    # 模型（混元 v3，锁定 hy3）
system: You are a helpful assistant.   # 系统提示

# MCP 服务器声明
mcp_servers:
  - name: building-wiki       # 服务器名，tools[].mcp_server_name 要引用它
    type: url                 # ⚠️ 只认 "url"（远程 HTTP MCP）；其它值被静默忽略
    url: https://<cloudrun-host>/mcp   # Streamable HTTP 端点
    # 可选：headers / 其它字段

# 工具挂载——mcp_servers 与 tools 必须成对出现
tools:
  - type: mcp_toolset
    mcp_server_name: building-wiki   # 必须 = mcp_servers[].name
    default_config:
      enabled: true
      # ⚠️ permission_policy 必须嵌在 default_config **里面**（曾误写成兄弟节点，被静默忽略）
      # 真码：dist/oak-runtime/config.js → t.default_config?.permission_policy?.type
      permission_policy:
        type: always_allow   # always_allow | always_ask
```

**硬约束（来自官方文档 + 实测）：**
1. `mcp_servers[].type` **只认 `url`**（远程 HTTP MCP）。其它类型字段会被**静默忽略**——写错不会报错但工具不生效。
2. `mcp_servers` 与 `tools` **必须成对**：声明了 server 但没在 `tools` 里挂 `mcp_toolset`，OAK **不会调用**它。
3. 工具在 Agent 侧的命名规则：`mcp__{serverName}__{toolName}`（例如 `mcp__building-wiki__compute_geometry`）。
4. `tools[].default_config.permission_policy.type`：`always_allow`（免确认直接调）或 `always_ask`（每次询问）。
   **必须嵌在 `default_config` 里面**——写成 `default_config` 的兄弟节点会被**静默忽略**（真码依据见上）。

---

## 2. 配置优先级（env 覆盖顺序）

```
AGENT_CONFIG / AGENT_CONFIG_B64 环境变量
        > agent.yaml 文件
        > AGENT_NAME / AGENT_MODEL / AGENT_SYSTEM 环境变量（这三个若存在会覆盖 yaml 同名项）
```

- 想整段覆盖配置：用 `AGENT_CONFIG`（JSON 字符串）或 `AGENT_CONFIG_B64`（base64）。
- 只改单项的快捷 env：`AGENT_NAME` / `AGENT_MODEL` / `AGENT_SYSTEM`。

---

## 3. MCP Server 硬约束（我们的 /mcp 端点必须遵守）

来自 MCP 官方协议 + OAK 接入实测：

1. **传输**：Streamable HTTP（SSE 流模式，非纯 JSON）。
2. **Stateless 模式**：`StreamableHTTPSessionManager(stateless=True)`，`sessionIdGenerator: undefined`。
   - 每个请求独立、无持久 SSE 长连接。
   - 无状态模式天然规避了「Cloud Run 30s 超时」问题——不存在需要保持 300s 的常驻长连接。（注：「Cloud Run 30s / MCP 需 ≥300s」旧说法**经核查官方文档未见依据，已弃用**。）
3. **Accept 头**：客户端请求**必须带** `Accept: application/json, text/event-stream`，否则服务端返回 **406**。OAK 客户端会自动带，自测时用 curl 也要带。
4. **工具名**：`mcp__{serverName}__{toolName}`。

---

## 4. Python mcp SDK = ASGI（必须换容器运行时）

`mcp` 官方 SDK（Python）是 **ASGI**（starlette + uvicorn，约 28 个依赖，含 cryptography / rpds-py 原生扩展）。

- `StreamableHTTPServerTransport.handle_request(self, scope, receive, send)` 是**纯 ASGI 接口**，无法塞进标准库 `http.server`。
- **结论**：容器从 `http.server` 切换到 **Starlette + uvicorn**。
- **挂载方式**：用 `FastMCP` 定义工具，再取底层 server 挂到 `StreamableHTTPSessionManager(stateless=True)`，最后把 `session_manager.handle_request` Mount 到 Starlette 的 `/mcp`。
- 选用 SSE 流模式（`json_response=False`，即默认），兼容性最好。

### 最小骨架（待实测确认属性名后再定稿）

```python
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from contextlib import asynccontextmanager
import uvicorn

mcp = FastMCP("building-wiki")

@mcp.tool()
def ping() -> str:
    return "pong"

# 挂到 /mcp（stateless）
session_manager = StreamableHTTPSessionManager(
    app=mcp._mcp_server,   # ⚠️ 属性名待 pip 安装后 introspect 确认
    stateless=True,
)

@asynccontextmanager
async def lifespan(app):
    async with session_manager.run():
        yield

app = Starlette(
    routes=[Mount("/mcp", app=session_manager.handle_request)],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 8000)))
```

> 注意：`mcp._mcp_server` 的属性名以实际安装版本 introspect 为准（可能是 `_mcp_server` 或 `mcp_server`）。写代码前必实跑确认。

---

## 5. Cloud Run 部署要点

- **Access Type 必须 `WEB`**（公网可达，否则 Agent 的 HTTP 函数调不到）。
- 生产 `Min Instances = 1`（避免冷启动；当前 `building-wiki` 容器已 `MinNum=1`）。
- 环境变量：`TCB_ENV_ID` / `TCB_API_KEY` / `TCB_AI_MODEL`（容器内 `_env_id()` 取不到环境 ID，**必须显式传 `TCB_ENV_ID`**，Dockerfile 不 COPY cloudbaserc.json）。
- Dockerfile 须加 `COPY requirements.txt .` + `pip install -r requirements.txt`。

---

## 6. 红线（来自项目长期记忆 §13.4#1）

**LLM 不得接触坐标 / 几何量。**

> 2026-09-22 收窄：原表述「任何数字」过宽。LLM **可**声明业务量（进数、面阔、进深等），
> 但取值必须来自知识中心（`siheyuan.rules:paramRanges` 等）；坐标、朝向、镜像、
> 「由尺寸推坐标」的运算仍属红线。

仅把以下两个函数作为 MCP 工具暴露给 Agent（再加一个 `ping` 做冒烟）：
- `compute_geometry(instance)` —— ④ 实例 → 构件清单（连续几何、绝对坐标、米、Y-up）
- `geometry_to_boxes(geometry)` —— ⑤ 构件 → 体素 BOX 清单

Agent（LLM）只负责自然语言 ↔ 实例图谱；坐标 / 几何量全在引擎里算。

---

## 7. 已确认的事实清单（避免重复踩坑）

- OAK 控制台模板 = OAK 项目，控制台「cloudbase-agent」模板即此。
- Agent 端点 `/acp`（实测）。
- `agent.yaml` 三个必填：`name` / `model` / `system`。
- `mcp_servers.type` 仅 `url` 生效。
- 声明与挂载必须成对。
- MCP 请求缺 `Accept: application/json, text/event-stream` → 406。
- Python mcp SDK 是 ASGI，容器要换 Starlette/uvicorn。
- 红线：LLM 不碰坐标/几何量（业务量可取，但值域来自知识中心），只暴露 compute_geometry / geometry_to_boxes（+ping）。

---

## 8. 落地机制（2026-09-21 实测，agent.yaml 已上线）

- **MCP 通道可更新 Agent 代码**（tcb 未登录也能做）：
  `manageAgent(action="updateAgent", agentId=..., cwd=<agent 代码目录>, installDependency=true, runtime="Nodejs20.19")`
  → 返回「代码更新完成（~6s）→ 配置更新完成（~86s）」。`cwd` 即 agent 代码目录本身（非「函数名子目录」）。
- **只需上传源码，不要传 `node_modules`**：代码包里的 19,775 个 `node_modules` 文件是**部署时云端装的**（实证：其 zip 时间戳 = 部署时刻，而 38 个源码文件时间戳更早）。`installDependency=true` 时平台会自动装依赖。
- **`scf_bootstrap` 的执行位由平台设置**：重部署后实测为 `0o777`，不必担心本地（Windows）打包丢执行权限。
- **部署后自检**：重新下载代码包读 `/agent.yaml` 比对；或在包内用真实 loader 跑一遍
  （`node_modules/open-managed-agent-runtime-shared` 的 `loadAgentConfig`）。
- **CLS 未开通时读不到启动日志**（`checkLogService → enabled:false`、`getAgentLogs → topic not exist`），
  此时无法远程确认 `[Config] Loaded…` / `[Agent] MCP Servers: N configured`，只能靠上述静态自检 + 控制台发一条对话。
- Agent 的对外域名形如 `https://agt-<agentId>.agent.tcloudbase.com/`（`DomainType=AI_AGENT`，上游 `WEB_SCF`）。
