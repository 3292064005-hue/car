export type CommandDecisionLevel = 'allow' | 'soft_warn' | 'hard_deny';
export type CommandDecisionSource = 'normal' | 'readonly' | 'authoritative_permission' | 'local_guard';

export interface CommandDecision {
  level: CommandDecisionLevel;
  reason: string;
  source: CommandDecisionSource;
  authoritative: boolean;
}


export interface ReadonlyBoundarySnapshot {
  demoReadonly: boolean;
  sessionWriteEnabled?: boolean;
  sessionAccessReason?: string;
  websocketSurfaceKind?: string;
  websocketSurfaceAuthority?: string;
}

/**
 * Evaluate whether the current frontend session is allowed to emit any write command.
 *
 * All outbound commands in this console are write-intent operations. Once the
 * browser is attached to a readonly session or the 9001 observer surface, the
 * browser must hard-deny the send before any command-specific permission logic
 * runs.
 *
 * @param snapshot Stable connection/UI snapshot used for send-time gating.
 * @param type Requested outbound command type label.
 * @returns A hard-deny decision when the session is readonly, otherwise `null`.
 * @throws Does not throw. All boundary failures are encoded in the returned decision.
 */
export function evaluateReadonlyBoundary(snapshot: ReadonlyBoundarySnapshot, type: string): CommandDecision | null {
  void type;
  if (snapshot.demoReadonly) {
    return {
      level: 'hard_deny',
      reason: '当前启用了本地演示锁，浏览器侧已阻止写操作；最终权限仍以后端权威会话为准。',
      source: 'readonly',
      authoritative: false,
    };
  }
  if (snapshot.sessionWriteEnabled === false) {
    return {
      level: 'hard_deny',
      reason: snapshot.sessionAccessReason ?? '当前会话已被后端标记为只读，所有写命令必须改走 9100 API facade。',
      source: 'readonly',
      authoritative: true,
    };
  }
  if (snapshot.websocketSurfaceKind === 'bridge_observer' || snapshot.websocketSurfaceAuthority === 'observer_only') {
    return {
      level: 'hard_deny',
      reason: '当前连接的是 9001 只读 bridge observer 面，所有写命令必须改走 9100 API facade。',
      source: 'readonly',
      authoritative: true,
    };
  }
  return null;
}
