/**
 * Kernel adapter — bridges open-agent-kernel's AcpStreamMessage stream to
 * the ACP wire protocol used by `./acp-endpoint.ts`.
 *
 * Since kernel v0.1.0-beta.8+, session.send() / respondApproval() /
 * respondToolUse() return `AsyncIterable<AcpStreamMessage>`. The kernel's
 * built-in AcpStreamAdapter envelopes EVERY yielded item as a JSON-RPC
 * message:
 *
 *   - plain Claude SDK messages  → `session/update` NOTIFICATION
 *       ({ jsonrpc, method:"session/update", params:{ sessionId, update } })
 *   - client tool / AskUserQuestion → `client/<ToolName>` JSON-RPC REQUEST
 *       ({ jsonrpc, id:"<sessionId>:<toolCallId>", method:"client/<Name>",
 *          params:{...input}, _meta:{ sessionId, toolCallId, assistantMessageId } })
 *   - HITL permission interrupt → `session/request_permission` JSON-RPC REQUEST
 *       ({ jsonrpc, id:"<sessionId>:<toolCallId>", method:"session/request_permission",
 *          params:{ sessionId, toolCall:{...}, options:[...] } })
 *
 * This module is a thin pass-through: it forwards each frame to the SSE sink
 * verbatim (only normalizing `sessionId`), and watches for the two stop-and-
 * resume triggers (request_permission / client tool) to end the turn with the
 * right stopReason. We NEVER re-wrap a frame — the kernel already envelopes.
 *
 * Stop-and-resume model (no reverse-RPC, no in-memory pending state):
 *
 *   1. `session/request_permission` request → turn paused, stopReason=
 *      "awaiting_permission". Client resumes via a fresh `session/prompt`
 *      with a `permission_decision` block → `session.respondApproval()`.
 *
 *   2. `client/<ToolName>` request (client tool / AskUserQuestion) → turn
 *      paused, stopReason="tool_use". Client resumes with a `tool_result`
 *      block → `session.respondToolUse()`.
 *
 *   3. `session/update` carrying `agent_phase: idle` → turn complete,
 *      stopReason="end_turn".
 *
 * Note on AskUserQuestion: the kernel's `AcpSessionUpdate` d.ts marks the
 * `ask_user` variant `@deprecated ... now flows through request_permission`,
 * but that comment is stale — the beta.14 dist de-specializes AskUserQuestion
 * into an ordinary client-tool (`isAskUserQuestion = bareToolName ===
 * "AskUserQuestion"`, emitted via `client/AskUserQuestion`), and the `ask_user`
 * variant is fully removed (0 occurrences in dist). So AskUserQuestion pauses
 * with `stopReason="tool_use"` and resumes via `respondToolUse`, exactly like a
 * custom client tool — NOT via `request_permission`/`respondApproval`.
 *
 * No service-side state is held between requests. The same conversation can
 * resume on a different runtime instance (kernel session store is the SoR).
 */
import type { Response } from "express";
import { type Agent as KernelAgent, type AcpStreamMessage, type ApprovalDecision, type PermissionOption, type Session as KernelSession, type ToolDefinition } from "@cloudbase/open-agent-kernel";
import type { AgentConfig } from "../config.js";
/**
 * Subset of CloudBaseSessionStore (declared via duck typing) we need at the
 * ACP layer for synchronous index writes. Kernel exposes the store as
 * `unknown` to avoid leaking SDK types into the public surface — we re-narrow
 * it here only for the single ACP code path that needs it.
 */
export interface SessionStoreLike {
    registerSession?: (args: {
        projectKey: string;
        sessionId: string;
        userId: string;
        title?: string;
        metadata?: Record<string, unknown>;
    }) => Promise<void>;
}
/** Build (or return cached) kernel Agent for this process. */
export declare function getKernelAgent(config: AgentConfig): KernelAgent;
/** Diagnostic: report whether the fix landed and the store hookup is live. */
export declare function getStoreDiag(): {
    agentInitialized: boolean;
    storeCaptured: boolean;
    hasRegisterSession: boolean;
    storeProto: string | null;
    lastSyncRegister: {
        sessionId: string;
        ok: boolean;
        error?: string;
        ts: number;
    } | null;
};
/**
 * Block on writing the session index row (oak_sessions) for the given
 * sessionId. Idempotent per the driver: where().limit(1).get() then update
 * OR add. Safe to call after every kernel startSession to close the race
 * against instance recycling on serverless.
 *
 * Returns false (and logs) when no store is configured or the store doesn't
 * implement registerSession — the caller should treat this as "best-effort,
 * not guaranteed visible in session/list yet".
 *
 * Outcome is recorded in `_lastSyncRegister` for the /healthz probe.
 */
export declare function syncRegisterSession(sessionId: string, userId: string, title?: string): Promise<boolean>;
/**
 * Get a kernel `Session` for the given ACP sessionId, creating it (via
 * `startSession`) or resuming it (via `resumeSession`) on first access.
 */
export declare function getOrCreateKernelSession(config: AgentConfig, acpSessionId: string, opts?: {
    userId?: string;
    isNew?: boolean;
}): Promise<KernelSession>;
export declare function dropKernelSession(acpSessionId: string): void;
export declare function abortKernelSession(acpSessionId: string): Promise<boolean>;
/** Pre-populate the pool with a kernel session created externally. */
export declare function registerKernelSession(acpSessionId: string, session: KernelSession): void;
/** ACP-shaped permission outcome (per spec §session/request_permission). */
export type ApprovalOutcome = {
    outcome: "selected";
    optionId: string;
} | {
    outcome: "cancelled";
};
export declare function outcomeToDecision(outcome: ApprovalOutcome): ApprovalDecision;
interface SseSink {
    write: (frame: unknown) => void;
    flush?: () => void;
    getAll?: () => string;
}
interface StreamCtx {
    sse: SseSink;
    rpcId: unknown;
    acpSessionId: string;
}
export type StopReason = "end_turn" | "cancelled" | "error" | "tool_use" | "awaiting_permission";
export interface PendingToolUse {
    toolUseId: string;
    toolName: string;
    input: unknown;
}
export interface PendingPermission {
    toolUseId: string;
    toolName: string;
    args: unknown;
    options: PermissionOption[];
}
export interface PumpResult {
    stopReason: StopReason;
    pendingToolUse?: PendingToolUse;
    pendingPermission?: PendingPermission;
}
/**
 * Pump kernel AcpStreamMessage stream into ACP SSE frames.
 *
 * The kernel's AcpStreamAdapter already envelopes every item (see module
 * doc). We forward each frame verbatim — only normalizing `sessionId` inside
 * `params` — and break out of the loop on the two stop-and-resume triggers so
 * the caller can end the SSE stream with the right stopReason.
 *
 * Three frame shapes (new enveloping kernel only):
 *
 *   1. `session/update` NOTIFICATION — forwarded as-is; if its `update` is
 *      `agent_phase: idle`, the turn is complete → stopReason="end_turn".
 *
 *   2. `session/request_permission` REQUEST — forwarded as-is; turn paused →
 *      stopReason="awaiting_permission", pendingPermission from params.
 *
 *   3. `client/<ToolName>` REQUEST (client tool / AskUserQuestion) — forwarded
 *      as-is; turn paused → stopReason="tool_use", pendingToolUse from params.
 *
 * Double-wrapping is avoided: an already-enveloped frame is forwarded as-is,
 * never re-wrapped. The kernel always envelopes (beta.14), so every item is
 * a JSON-RPC frame — no bare-update fallback is needed.
 *
 * Returns the final stopReason and, when the turn was paused for an external
 * action, a pendingToolUse or pendingPermission payload describing what the
 * client must do to resume.
 */
export declare function pumpEvents(events: AsyncIterable<AcpStreamMessage>, ctx: StreamCtx): Promise<PumpResult>;
export declare function makeSseSink(res: Response): SseSink;
export declare function makeClientSideToolDefinition(tool: {
    name: string;
    description: string;
    input_schema: Record<string, unknown>;
}): ToolDefinition;
export {};
