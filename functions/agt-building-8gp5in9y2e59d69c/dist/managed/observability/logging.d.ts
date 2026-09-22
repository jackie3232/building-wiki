/**
 * Managed runtime logging (evlog). Skill materialization + cold-start diagnostics.
 */
export declare function isManagedLogDebug(): boolean;
export declare function initManagedLogging(): void;
export interface ManagedLogHandle {
    set(fields: Record<string, unknown>): void;
    phase(name: string, fields?: Record<string, unknown>): void;
    milestone(name: string, fields?: Record<string, unknown>): void;
    error(err: unknown, fields?: Record<string, unknown>): void;
    emit(extra?: Record<string, unknown>): void;
}
export declare function managedLog(scope: Record<string, unknown>): ManagedLogHandle;
export declare function managedTrace(scope: string, fields?: Record<string, unknown>): void;
