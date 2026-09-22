/**
 * OAK session cwd — kernel AgentConfig.cwd and skill materialize target.
 * Keep `scf_bootstrap` OAK_WORKSPACE_CWD in sync with {@link OAK_WORKSPACE_CWD}.
 */
/** OAK kernel `cwd` + `.claude/skills/` materialize root (SCF + TCBR). */
export declare const OAK_WORKSPACE_CWD = "/tmp/workspace";
/** Ensures writable session cwd exists; cached for process lifetime. */
export declare function resolveOakWorkspaceCwd(): string;
