/* BUILDING.WIKI · 前端配置（非敏感项写死在这里；密钥从 config.local.js 覆盖）
 *
 * Publishable Key 的性质：它只是「应用标识」，本身零权限，真正决定能做什么的是
 * 服务端的来源（Origin）校验与登录态 —— 所以它可以进前端源码。但仍不进日志、
 * 不进仓库：真实值放 config.local.js（已 gitignore），本文件只留空占位。
 */
window.BW_CONFIG = Object.assign({
  // 云托管容器（MCP 宿主）
  MCP_URL: "https://building-wiki-310221-6-1258039591.sh.run.tcloudbase.com/mcp/",
  // OAK Agent 的 ACP 端点
  ACP_URL: "https://building-wiki-d3gm9k9xwd651699f.api.tcloudbasegateway.com" +
           "/v1/aibot/bots/agt-building-8gp5in9y2e59d69c/acp",
  // 由 config.local.js 覆盖；为空则页面提示补配置
  PUBLISHABLE_KEY: "",
}, window.BW_LOCAL || {});
