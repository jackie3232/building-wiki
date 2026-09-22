/**
 * OpenManagedAgent — Managed runtime entry (standalone).
 *
 * Only the managed (OAK) kernel is loaded here — no harness code, no dispatcher.
 * Deployed as SCF / TCBR for `runtime: managed` agents.
 *
 * 部署方式：
 *   tcb agent create --name my-agent --code ./packages/agent-runtime-managed -e $ENV_ID
 *
 * 暴露端点：
 *   POST /acp                              ACP JSON-RPC 2.0
 *   POST /send-message                     ACP alias (compat path)
 *   POST /v1/aibot/bots/:botId/acp         ACP via gateway proxy
 *   POST /v1/aibot/bots/:botId/send-message  ACP alias via gateway proxy
 *   GET  /healthz                          Health check
 */
export {};
