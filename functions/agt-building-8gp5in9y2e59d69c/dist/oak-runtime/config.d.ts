/**
 * OAK runtime config — kernel AgentConfig mapping.
 *
 * Extracted from `src/config.ts` to keep the OAK-specific `toKernelAgentConfig`
 * (and its `@cloudbase/open-agent-kernel` type dependencies) physically
 * separate from the shared `AgentConfig` schema. Both modes (oak + harness)
 * still share `AgentConfig`, `getCustomTools`, `resolveBuiltinTools`,
 * `getMcpToolsets` from `../config.js`.
 */
import { type AgentConfig as KernelAgentConfig, type ToolDefinition } from "@cloudbase/open-agent-kernel";
import { type AgentConfig } from "../config.js";
export interface ToKernelOptions {
    /** Override envId; default reads CLOUDBASE_ENV_ID env var */
    envId?: string;
    /** ToolDefinition[] built from AgentConfig.tools[type=custom], passed by kernel-adapter */
    customToolDefs?: ToolDefinition[];
}
/**
 * Translate the YAML-shaped `AgentConfig` into a kernel `AgentConfig`.
 *
 * Kernel beta now handles most defaults declaratively:
 *   - `credentials` → auto-creates CloudBaseDbDriver for session/permission store
 *   - `sandbox: { enabled: true }` → auto-creates AgsStatefulSandbox
 *   - `session: { enabled: true }` → auto-creates CloudBaseSessionStore + driver
 *
 * We no longer manually instantiate CloudBaseDbDriver / CloudBaseSessionStore /
 * AgsStatefulSandbox / InMemoryPermissionStore.
 */
export declare function toKernelAgentConfig(config: AgentConfig, opts?: ToKernelOptions): KernelAgentConfig;
