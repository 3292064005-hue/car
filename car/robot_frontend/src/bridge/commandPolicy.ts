import { createEnvelope } from '@/bridge/protocol';
import { evaluateReadonlyBoundary, type CommandDecision, type CommandDecisionLevel, type CommandDecisionSource } from '@/bridge/policyKernel';
import { canTransitionMode } from '@/machines/modeRules';
import { summarizeInspectorRaw } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';
import type { BridgeOutboundEvent, BridgeOutboundPayloadMap, CommandType } from '@/types/robot';

export interface PreparedCommand<TType extends CommandType = CommandType> {
  envelope: BridgeOutboundEvent;
  summary: string;
  type: TType;
}

function priorityFor(type: CommandType): 'normal' | 'high' | 'critical' {
  if (type === 'estop') return 'critical';
  if (type === 'set_mode' || type === 'teleop_cmd' || type === 'start_patrol') return 'high';
  return 'normal';
}

function needsExplicitConfirmation(type: CommandType): boolean {
  return type === 'estop' || type === 'start_patrol';
}

function permissionReason(type: CommandType): string {
  const { connection } = useRobotStore.getState();
  const permission = connection.commandPermissions?.[type];
  if (!permission || permission.allowed !== false) return '';
  return permission.reason ?? `后端权威快照提示该命令当前不可用：${type}`;
}

function hasAuthoritativePermission(type: CommandType): boolean {
  const { connection } = useRobotStore.getState();
  return Boolean(connection.commandPermissions && type in connection.commandPermissions);
}

function authoritativePermissionLevel(type: CommandType): CommandDecisionLevel {
  switch (type) {
    case 'stop_now':
    case 'estop':
    case 'resume_from_safe_stop':
    case 'reset_fault':
      return 'soft_warn';
    default:
      return 'hard_deny';
  }
}

function readonlySessionDecision<TType extends CommandType>(type: TType): CommandDecision | null {
  const { connection, ui } = useRobotStore.getState();
  return evaluateReadonlyBoundary({
    demoReadonly: ui.demoReadonly,
    sessionWriteEnabled: connection.sessionWriteEnabled,
    sessionAccessReason: connection.sessionAccessReason,
    websocketSurfaceKind: connection.websocketSurfaceKind,
    websocketSurfaceAuthority: connection.websocketSurfaceAuthority,
  }, type);
}

function localGuardDecision<TType extends CommandType>(type: TType, payload: BridgeOutboundPayloadMap[TType]): CommandDecision {
  const store = useRobotStore.getState();
  if (type === 'set_mode') {
    const targetMode = (payload as BridgeOutboundPayloadMap['set_mode']).mode;
    const rule = canTransitionMode({
      currentMode: store.motion.mode,
      targetMode,
      fault: store.fault,
      connection: store.connection,
      power: store.power,
    });
    if (!rule.allowed) {
      return {
        level: 'hard_deny',
        reason: rule.reason ?? `当前不允许切换到 ${targetMode}`,
        source: 'local_guard',
        authoritative: Boolean(store.connection.commandPermissions?.set_mode || store.connection.allowedTargetModes),
      };
    }
    if (rule.reason) {
      return { level: 'soft_warn', reason: rule.reason, source: 'local_guard', authoritative: false };
    }
    return { level: 'allow', reason: '', source: 'normal', authoritative: false };
  }

  if (!hasAuthoritativePermission(type)) {
    if (type === 'teleop_cmd' && store.motion.mode !== 'MANUAL') {
      return {
        level: 'soft_warn',
        reason: '本地提示：非 MANUAL 模式持续 teleop 存在被拒绝风险，最终以桥接 ACK 为准。',
        source: 'local_guard',
        authoritative: false,
      };
    }
    if (type === 'start_patrol' && (store.power.lowPowerWarning || store.runtime.safetyPhase === 'fault_locked')) {
      return {
        level: 'soft_warn',
        reason: '本地提示：低压或故障锁定状态下启动巡检存在被拒绝风险，最终以后端裁决为准。',
        source: 'local_guard',
        authoritative: false,
      };
    }
  }

  return { level: 'allow', reason: '', source: 'normal', authoritative: false };
}

/**
 * Evaluate the current outbound command against readonly state, authoritative
 * permissions, and local guards.
 *
 * @param type Command type requested by the caller.
 * @param payload Command payload that may carry target mode or motion values.
 * @returns Decision with level/reason/source metadata for UI hints and send-time gating.
 * @throws Does not throw; all rejection paths are encoded in the returned decision.
 * @remarks Readonly state is treated as a hard deny for all writes. Authoritative
 * permission snapshots override local guards when present; otherwise local guards only emit
 * soft guidance unless a mode transition is structurally invalid.
 */
export function evaluateCommandDecision<TType extends CommandType>(type: TType, payload: BridgeOutboundPayloadMap[TType]): CommandDecision {
  const store = useRobotStore.getState();

  const readonlyDecision = readonlySessionDecision(type);
  if (readonlyDecision) {
    return readonlyDecision;
  }

  if (hasAuthoritativePermission(type)) {
    const reason = permissionReason(type);
    if (reason) {
      return {
        level: authoritativePermissionLevel(type),
        reason,
        source: 'authoritative_permission',
        authoritative: true,
      };
    }
  }

  return localGuardDecision(type, payload);
}

/**
 * Convert a command decision into button-facing state.
 *
 * @param type Command type bound to the button.
 * @param payload Payload preview used to evaluate policy.
 * @returns Disabled flag, human-readable reason, and the raw decision.
 * @throws Does not throw; invalid states are surfaced through the returned decision.
 * @remarks Only hard-deny decisions disable the control. Soft warnings keep the button
 * interactive so the backend/bridge ACK remains the final authority.
 */
export function commandButtonState<TType extends CommandType>(type: TType, payload: BridgeOutboundPayloadMap[TType]): { disabled: boolean; reason: string; decision: CommandDecision } {
  const decision = evaluateCommandDecision(type, payload);
  return {
    disabled: decision.level === 'hard_deny',
    reason: decision.reason,
    decision,
  };
}

function writeDecisionLog(summary: string, decision: CommandDecision): void {
  const store = useRobotStore.getState();
  if (decision.level === 'allow') return;
  const domain = decision.source === 'authoritative_permission' || decision.source === 'readonly' ? 'SAFETY' : 'SYSTEM';
  const detail = decision.reason || `命令 ${summary} 被策略拒绝`;
  if (decision.level === 'hard_deny') {
    store.setRuntimeRejection(detail);
    store.pushLog({ level: 'WARN', domain, message: `命令未发送：${summary}`, details: detail });
    return;
  }
  store.pushLog({ level: 'WARN', domain, message: `命令携带风险提示，继续发送：${summary}`, details: detail });
}

/**
 * Build a sendable outbound envelope after applying command policy and optional confirmation.
 *
 * @param type Command type to dispatch.
 * @param payload Serialized command payload.
 * @param summary Human-readable action summary used in logs and confirmations.
 * @param seq Monotonic outbound sequence number owned by the bridge client.
 * @returns Prepared command envelope when sending is allowed; otherwise `null`.
 * @throws Does not throw for policy rejection; readonly/permission/local-guard denials and
 * user-cancelled confirmations return `null` after runtime rejection/log side effects.
 * @remarks Boundary behavior is intentional: hard-deny stops the send, soft-warn logs and
 * continues, and dangerous commands may require explicit user confirmation in browser contexts.
 */
export function prepareOutboundCommand<TType extends CommandType>(type: TType, payload: BridgeOutboundPayloadMap[TType], summary: string, seq: number): PreparedCommand<TType> | null {
  const store = useRobotStore.getState();
  const decision = evaluateCommandDecision(type, payload);
  writeDecisionLog(summary, decision);
  if (decision.level === 'hard_deny') return null;

  if (needsExplicitConfirmation(type) && typeof window !== 'undefined') {
    const confirmed = window.confirm(`确认执行命令：${summary}？`);
    if (!confirmed) {
      store.setRuntimeRejection(`操作已取消：${summary}`);
      return null;
    }
  }

  const envelope = createEnvelope({
    type,
    payload,
    sessionId: store.connection.transportLabel || 'frontend-session',
    seq,
    reason: summary,
    dedupeKey: type === 'teleop_cmd' ? `teleop:${(payload as BridgeOutboundPayloadMap['teleop_cmd']).linear}:${(payload as BridgeOutboundPayloadMap['teleop_cmd']).angular}` : undefined,
  });

  store.recordTrace('out', type, summarizeInspectorRaw(envelope), 'sent');
  store.enqueueCommand(envelope.eventId, type, summary, priorityFor(type), Boolean(envelope.dangerous));
  store.setRuntimeRejection(null);
  return { envelope, summary, type };
}
