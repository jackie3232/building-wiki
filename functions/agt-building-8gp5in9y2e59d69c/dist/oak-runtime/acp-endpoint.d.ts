/**
 * OAK runtime ACP (Agent Client Protocol) endpoint — backed by open-agent-kernel.
 *
 * Wire format unchanged from the previous (HunyuanAgent) implementation.
 * Underlying agent loop is @cloudbase/open-agent-kernel.
 *
 * Transport:
 *   - JSON-RPC 2.0 over HTTP POST
 *   - Streaming uses SSE (`text/event-stream`), `data: <json>\n\n` frames,
 *     terminated by `data: [DONE]\n\n`.
 *
 * Endpoints (both routes share the same handler):
 *   POST /acp                              Direct ACP entry
 *   POST /v1/aibot/bots/:botId/acp         Gateway path (deployment-only)
 *
 * Supported JSON-RPC methods:
 *   initialize                Capability negotiation
 *   session/new               Create session
 *   session/list              List sessions
 *   session/load              Load session (replay=true → SSE history_page)
 *   session/prompt            SSE: agent_message_chunk / tool_call(_update)
 *                             May pause with stopReason='awaiting_permission'
 *                             (session/request_permission REQUEST) or
 *                             stopReason='tool_use' (client/<ToolName> REQUEST,
 *                             incl. AskUserQuestion)
 *   session/cancel            Notification: abort the in-flight prompt
 *   session/delete            Idempotent delete (ACP spec extension)
 *
 * Reverse RPC (agent → client) — HITL:
 *   request_permission            Sent inside the SSE stream as a JSON-RPC
 *                                 session/update notification. Client resumes
 *                                 by POSTing a fresh session/prompt with a
 *                                 permission_decision block whose decision
 *                                 field carries the selected optionId.
 */
import type { Express } from "express";
import type { AgentConfig } from "../config.js";
export declare function mountManagedAcpEndpoint(app: Express, agentConfig: AgentConfig): void;
