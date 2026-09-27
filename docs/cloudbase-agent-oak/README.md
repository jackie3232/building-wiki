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
3. 工具在 Agent 侧的命名规则：`mcp__{serverName}__{toolName}`（例如 `mcp__building-wiki__generate_building`）。
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

仅把**一个业务工具**暴露给 Agent（再加一个 `ping` 做冒烟）：
- `generate_building(instance_ref)` —— by-reference 单入口：读回实例图谱 → 硬闸 → ④ 实例 → 构件清单 → ⑤ 构件 → 体素 BOX 清单

> 2026-09-27 收窄：原 `compute_geometry` / `geometry_to_boxes` 两个工具已删除，改为 `generate_building` 的内部步骤
> （它们是「前端两步直连」时代的遗留；全 Agent 形态下 Agent 只需认识一个几何工具）。

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
- 红线：LLM 不碰坐标/几何量（业务量可取，但值域来自知识中心），MCP 只暴露 `generate_building` 单入口（+ping）。

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

---

## 9. 官方文档补充记录（2026-09-27，用户逐页粘贴 + 对话整理落盘）

> 来源：docs.cloudbase.net/ai 官方文档 6 页。定位：本节是 §0~§8 的官方文档增量补充，
> 与旧记录冲突时以本节为准（更晚、更权威）。

### 9.1 《AI Agent 开发概述》——Route A 入口页

- 框架适配三条路：LangChain / LangGraph / CrewAI，全部走 `@cloudbase/agent-adapter-*` → **AG-UI 协议**。
- 部署两种：HTTP 云函数 / 云托管。
- 模型网关 `https://{envId}.api.tcloudbasegateway.com/v1/ai/cloudbase` + `TCB_API_KEY`——与我们实测（provider=cloudbase + hy3）一致。
- 我们走 Route B（OAK/ACP），本页属 Route A；文档树确认：本地开发 / Agent UI 组件 / 云开发Agent模板 / 可观测性 / 部署·上线·调用指南。

### 9.2 《AG-UI 协议》——Route A 协议概览

- ★官方盖章 Route 划分（原话）："云开发 Agent 的通信协议由创建时的模板决定：**自建 HTTP Agent 使用 AG-UI 协议；基于 cloudbase-agent 模板创建的 Agent 使用 ACP 协议**，其控制台端点以 /acp 结尾。"
- 事件五族：`RUN_*`（生命周期）/ `TEXT_MESSAGE_*`（消息增量）/ `TOOL_CALL_*`（工具）/ `STATE_SNAPSHOT·STATE_DELTA·MESSAGES_SNAPSHOT`（状态）/ `STEP_*`（步骤）。
- 人机交互：AG-UI **借用 TOOL_CALL 事件**模拟确认/输入；OAK 用 `session/request_permission` 帧——概念对照：
  | AG-UI（Route A） | OAK/ACP（Route B，我们） |
  |---|---|
  | `RUN_*`+`TEXT_MESSAGE_*` | `session/update` 帧 `agent_message_chunk` |
  | `TOOL_CALL_*` | `tool_call / tool_call_update` |
  | 用户确认（借 TOOL_CALL） | HITL `session/request_permission` |
  | 自建 `POST /agent` | 控制台端点 `/acp` |

### 9.3 《前后端通信协议》（POST /send-message）——AG-UI 完整规范

- ★已知坑（原话）："基于 cloudbase-agent 模板创建的 Agent 使用 ACP 协议：其 **/send-message 路径同样存在，但请求体为 ACP（JSON-RPC 2.0）格式，按本文的 RunAgentInput 结构调用会返回 400**。"——前端直连我们 Agent 时**不能用 `@ag-ui/client` 的 HttpAgent**。
- `RunAgentInput`：threadId / runId / parentRunId（分支回溯）/ state / messages / tools / context / forwardedProps。
- 消息五型 developer/system/assistant/user/tool；**用户消息多模态**：`InputContent[]` 含 `{type:"binary", mimeType, url|data, filename}`。
- 事件比 9.2 多一个 `TOOL_CALL_RESULT`；`STATE_DELTA` = RFC 6902 JSON Patch；`TOOL_CALL_ARGS` 按 toolCallId 流式拼接（并行调用事件交错）。
- 前端工具判定：`TOOL_CALL_END` 后查工具名是否在请求 `tools` 列表——在=前端工具（**两轮请求**模式），不在=服务端工具（等 `TOOL_CALL_RESULT`）。
- OAK HITL 与 AG-UI 形态不同：OAK 是**会话内暂停**（`respondApproval()` 续跑），AG-UI 是**两轮 HTTP 请求**。前端接入别套错。

### 9.4 《本地开发》

- ★线上 Agent 真实调用 URL 形态（第三入口，新增记录）：
  `https://{envId}.api.tcloudbasegateway.com/v1/aibot/bots/agent-{agentId}/send-message`
- 同步线上代码到本地（部署后自检的官方途径）：
  `cloudbase fn code download -e <env> <fn> ./dir`（Agent 云函数）；`cloudbase cloudrun download -s <svc> --targetPath ./dir`（building-wiki 容器）。
- Whistle 代理调试：`w2 start` + 规则"线上 send-message URL → resCross://* http://localhost:9000/send-message"，客户端配 127.0.0.1:8899 代理 + 装 HTTPS 根证书。**传输层操作，对 ACP Agent 同样适用**。
- 模板清单（langchain/langgraph/crewai/adk/adp/coze/n8n 共 12 个）全属 Route A，与我们无关。

### 9.5 《OpenAgentKernel（官方 SDK）》——Route B 权威页

- 模型未开通报错：`403 AI_MODEL_NOT_SUPPORTED`。
- ★动态配置（官方推荐）：**systemPrompt / model 存云开发数据库配置表，云函数入口每次请求读取**——"人设、欢迎语、开场问题都成为数据而不是代码，改动它们和改一条数据库记录一样"。**这是「专家工件」的官方背书落点之一**（见 9.7）。
- 部署双路并存：`tcb fn code download → 改 → tcb fn deploy`（文档推荐）与 `manageAgent(action="updateAgent")` MCP 通道（§8，我们实测过的）。
- `stream` 字段：文档页有（默认 true；**网关层缓冲整个响应时前端仍要等整轮**），GitHub README 完整字段表**没列**——两处口径差异，以文档页为准。
- beta → 0.1.1 迁移：env `TCB_API_KEY`→`CLOUDBASE_APIKEY`；事件帧 `event.type`→`msg.params.update.sessionUpdate`；Node 22+→**20.19+**。待办：部署前静态核 `scf_bootstrap` 注入的 key 变量名与运行时版本匹配。

### 9.6 《常见问题 FAQ》

- ★计费分层（别误读）：免费/个人版 = 对话 + 人设/开场白/知识库/数据模型/联网搜索；**团队版及以上才加 MCP、语音、文件上传、多会话**。⚠️ 指**控制台可视化 Agent**产品；我们自建函数型 Agent（OAK）在个人版实测 MCP 可用。但官方口径 MCP 属"高级能力"，控制台侧使用可能受限。
- 错误码：401 认证失败 / 403 权限不足 / 429 请求过多 / 500。我们实测的 `429 EXCEED_TOKEN_QUOTA_LIMIT` 属 429 家族。
- 官方示例印证模型锁型：`ai.createModel("cloudbase")` + `streamText({ model: "hy3" })`。
- ★前端超时坑：**cloudbase-js-sdk 默认 15s 超时会主动取消请求**——调 Agent 须 `cloudbase.init({ timeout: 600000 })`；小程序端 `app.json` 配 `networkTimeout.request`（建议 ≤10 分钟）。viewer 将来经 SDK 调 Agent 必踩。
- 小程序接 AI 两路：微信**基础库** `wx.cloud.extend.AI`（不占包体积、免配域名，纯小程序优先）vs **AI SDK**（多端一致、占包体积、要配域名）。
- 合规：小程序用 AI 正式上线前须**深度合成算法资质备案** + 类目审核。
- 过期信息甄别："100 万 token 赠送活动"2025-12-31 截止已过期；与现状（credits 计费）吻合，不作依据。

### 9.7 对「专家工件」讨论的架构结论（本轮文档调研的目的）

- **OAK 世界观是两层**：`Agent(人设+接线) → skills`。createAgent 全部 20 字段中**无 expert/persona/专家概念**（README 全文无此词；`name` 仅回显、`metadata`/`description` 预留未读取）。
- skills 的确切语义：**不是 system prompt 硬注入，是 model-invoked tool**——OAK 只把 SKILL.md 的 frontmatter 注入 prompt，模型匹配场景时主动调 `Skill` 工具加载全文（examples/15-skills.ts 注释原话）。这就是我们必须在 `system:` 手写指路的原因。
- 平台原生资产落点：`cwd`（影响 skills 和**项目级 CLAUDE.md**）、`userMemory`（同步 CLAUDE.md/agent-memory 到云存储）、`hooks`（生命周期钩子，未用）。
- **「专家」的三个候选落点**（待用户拍板）：
  1. `cwd/CLAUDE.md`——平台原生识别，零新机制；注入语义**待实测**；
  2. `systemPrompt`（写死 agent.yaml）——现状，与运行时接线混装；
  3. **数据库配置表**——官方推荐"人设=数据"，改专家不重部署（9.5 动态配置）。
