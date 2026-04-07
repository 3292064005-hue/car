import { createEnvelope } from '@/bridge/protocol';
import { summarizeInspectorRaw } from '@/shared/utils';
import { useRobotStore, validateModeTransition } from '@/store/useRobotStore';
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


export function prepareOutboundCommand<TType extends CommandType>(type: TType, payload: BridgeOutboundPayloadMap[TType], summary: string, seq: number): PreparedCommand<TType> | null {
  const store = useRobotStore.getState();

  if (store.ui.demoReadonly && type !== 'speak_fixed_text') {
    store.setRuntimeRejection('当前处于只读演示模式，已拒绝写操作。');
    return null;
  }

  if (type === 'set_mode') {
    const rule = validateModeTransition((payload as BridgeOutboundPayloadMap['set_mode']).mode);
    if (!rule.allowed) {
      store.pushLog({
        level: 'WARN',
        domain: 'SAFETY',
        message: '模式切换存在风险提示，命令仍会发送，最终裁决以后端为准。',
        details: rule.reason ?? '模式切换存在风险提示'
      });
    }
  } else if (hasAuthoritativePermission(type)) {
    const reason = permissionReason(type);
    if (reason) {
      store.pushLog({
        level: 'WARN',
        domain: 'SAFETY',
        message: '后端权威快照提示该命令当前可能被拒绝，命令仍会发送以获取最终 ACK。',
        details: reason
      });
    }
  } else {
    if (type === 'teleop_cmd' && store.motion.mode !== 'MANUAL') {
      store.pushLog({ level: 'WARN', domain: 'SAFETY', message: '本地提示：非 MANUAL 模式持续 teleop 存在被拒绝风险。', details: '命令仍会发送，最终以桥接 ACK 为准。' });
    }
    if (type === 'start_patrol' && (store.power.lowPowerWarning || store.runtime.safetyPhase === 'fault_locked')) {
      store.pushLog({ level: 'WARN', domain: 'SAFETY', message: '本地提示：低压或故障锁定状态下启动巡检存在被拒绝风险。', details: '命令仍会发送，最终以后端裁决为准。' });
    }
  }

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
    dedupeKey:
      type === 'teleop_cmd' ? `teleop:${(payload as BridgeOutboundPayloadMap['teleop_cmd']).linear}:${(payload as BridgeOutboundPayloadMap['teleop_cmd']).angular}` : undefined,
  });

  store.recordTrace('out', type, summarizeInspectorRaw(envelope), 'sent');
  store.enqueueCommand(envelope.eventId, type, summary, priorityFor(type), Boolean(envelope.dangerous));
  store.setRuntimeRejection(null);
  return { envelope, summary, type };
}
