/**
 * Managed runtime — materialize deployment-bundle skills into OAK cwd layout.
 *
 * OAK / Claude Agent SDK expects: <cwd>/.claude/skills/<name>/SKILL.md
 * Deployment bundle stores:     <runtime-pkg>/skills/<name>/...
 *   SCF:  /var/user/skills/...   (runtime pkg root; process cwd is /tmp/workspace)
 *   TCBR: /app/skills/...        (WORKDIR /app)
 */
export interface MaterializeManagedSkillsResult {
    materialized: string[];
    skipped: string[];
}
export interface MaterializeManagedSkillsOptions {
    /** Bundle skills root (default: resolveBundleSkillsDir()). */
    bundleSkillsDir?: string;
    /** OAK session cwd (default: {@link resolveOakWorkspaceCwd}). */
    workspaceCwd?: string;
}
export interface ResolveBundleSkillsDirOptions {
    cwd?: string;
    /** Override runtime package root (tests); default: dirname(import.meta.url)/../.. */
    runtimePkgRoot?: string;
}
/** Destination SKILL.md path for a skill name under the OAK workspace cwd. */
export declare function oakSkillDestPath(workspaceCwd: string, skillName: string): string;
/**
 * Locate deploy-bundle skills/ regardless of process cwd.
 * SCF starts with cwd=/tmp/workspace but skills live under /var/user/skills.
 */
export declare function resolveBundleSkillsDirSync(opts?: ResolveBundleSkillsDirOptions): string;
export declare function resolveBundleSkillsDir(opts?: ResolveBundleSkillsDirOptions): Promise<string>;
/** Skill directory names present in the deploy bundle (sync). */
export declare function listBundledSkillNames(bundleSkillsDir: string): string[];
/**
 * Copy installed skills from the deployment bundle into OAK workspace layout.
 */
export declare function materializeManagedSkills(skillNames: string[], opts?: MaterializeManagedSkillsOptions): Promise<MaterializeManagedSkillsResult>;
