import { locallyAllowsTransition } from '@/generated/modeTransitions';
import type {
  ConnectionState,
  FaultState,
  PowerState,
  RobotMode,
  RuntimeState,
  TaskState
} from '@/types/robot';

type ModeSignal = 'BOOT_DONE' | 'ENTER_MANUAL' | 'START_PATROL' | 'ENTER_TRACK' | 'EXIT_TO_IDLE' | 'REQUEST_SAFE_STOP' | 'FAULT_RAISED' | 'RECOVER_TO_IDLE';

function signalForTarget(currentMode: RobotMode, targetMode: RobotMode): ModeSignal | null {
  if (currentMode === targetMode) return null;
  if (currentMode === 'BOOT' && targetMode === 'IDLE') return 'BOOT_DONE';
  if (targetMode === 'MANUAL') return 'ENTER_MANUAL';
  if (targetMode === 'PATROL') return 'START_PATROL';
  if (targetMode === 'TRACK') return 'ENTER_TRACK';
  if (targetMode === 'IDLE') return currentMode === 'FAULT' || currentMode === 'SAFE_STOP' ? 'RECOVER_TO_IDLE' : 'EXIT_TO_IDLE';
  if (targetMode === 'SAFE_STOP') return 'REQUEST_SAFE_STOP';
  if (targetMode === 'FAULT') return 'FAULT_RAISED';
  return null;
}

function guardTargetMode(input: {
  currentMode: RobotMode;
  targetMode: RobotMode;
  fault: FaultState;
  connection: ConnectionState;
  power: PowerState;
}): { allowed: boolean; reason?: string } {
  const { currentMode, targetMode, fault, connection } = input;

  const allowedTargetModes = connection.allowedTargetModes ?? [];
  const hasAuthoritativeContract = Array.isArray(connection.allowedTargetModes)
    || typeof connection.commandPermissions?.set_mode?.allowed === 'boolean'
    || typeof connection.safeStopRecoverable === 'boolean';

  if (hasAuthoritativeContract) {
    if (Array.isArray(connection.allowedTargetModes) && !allowedTargetModes.includes(targetMode)) {
      return { allowed: false, reason: connection.modeReasons?.[targetMode] ?? `后端未授权 ${currentMode} -> ${targetMode}` };
    }
    if (connection.commandPermissions?.set_mode?.allowed === false) {
      return { allowed: false, reason: connection.commandPermissions.set_mode.reason ?? '后端禁止当前模式切换请求' };
    }
    if (fault.safeStopActive && ['IDLE', 'MANUAL'].includes(targetMode) && connection.safeStopRecoverable === false) {
      return { allowed: false, reason: connection.safeStopBlockedReason ?? 'SAFE_STOP 尚不可恢复' };
    }
    return { allowed: true };
  }

  if (fault.safeStopActive && ['IDLE', 'MANUAL'].includes(targetMode) && connection.safeStopRecoverable === false) {
    return { allowed: true, reason: connection.safeStopBlockedReason ?? '本地提示：SAFE_STOP 尚不可恢复，最终以后端 ACK 为准' };
  }
  if (!locallyAllowsTransition(currentMode, targetMode)) {
    return { allowed: false, reason: `本地权威回退矩阵禁止 ${currentMode} -> ${targetMode}` };
  }
  return { allowed: true, reason: '本地回退矩阵允许该切换；最终以后端裁决为准' };
}

export function canTransitionMode(input: {
  currentMode: RobotMode;
  targetMode: RobotMode;
  fault: FaultState;
  connection: ConnectionState;
  power: PowerState;
}): { allowed: boolean; reason?: string; signal?: string } {
  const { currentMode, targetMode, fault, connection, power } = input;
  if (currentMode === targetMode) return { allowed: false, reason: '已经处于该模式' };

  const guard = guardTargetMode({ currentMode, targetMode, fault, connection, power });
  if (!guard.allowed) return guard;

  const signal = signalForTarget(currentMode, targetMode);
  if (!signal) return { allowed: true, reason: guard.reason };
  return { allowed: true, signal, reason: guard.reason };
}

export function deriveRuntimeState(input: {
  motionMode: RobotMode;
  fault: FaultState;
  connection: ConnectionState;
  power: PowerState;
  task: TaskState;
}): RuntimeState {
  const { motionMode, fault, connection, power, task } = input;

  let safetyPhase: RuntimeState['safetyPhase'] = 'nominal';
  if (fault.level === 'critical' && fault.code) safetyPhase = 'fault_locked';
  else if (fault.estopActive || fault.safeStopActive) safetyPhase = 'safe_stop';
  else if (power.lowPowerWarning || connection.reconnecting || connection.staleMotion || connection.stalePower || connection.staleVision || connection.staleVoice) safetyPhase = 'degraded';

  let taskPhase: RuntimeState['taskPhase'] = 'idle';
  if (task.patrolStatus === 'running') taskPhase = 'running';
  else if (task.patrolStatus === 'paused') taskPhase = 'paused';
  else if (task.patrolStatus === 'completed') taskPhase = 'completed';
  else if (task.patrolStatus === 'aborted') taskPhase = task.currentWaypoint ? 'interrupted' : 'aborted';

  let modeAudit = '系统待机';
  if (motionMode === 'BOOT') modeAudit = '系统引导中，仅允许进入 IDLE';
  else if (motionMode === 'MANUAL') modeAudit = '人工接管生效，deadman 必须保持';
  else if (motionMode === 'PATROL') modeAudit = '自动巡检执行中，关注 waypoint/异常';
  else if (motionMode === 'TRACK') modeAudit = '目标跟踪执行中，关注视觉偏差';
  else if (motionMode === 'SAFE_STOP') modeAudit = connection.safeStopRecoverable === false ? `安全停车中，恢复受阻：${connection.safeStopBlockedReason ?? '未知原因'}` : connection.safeStopRequiresManualAck ? '安全停车中，链路已恢复，等待人工确认' : '安全停车中，等待恢复确认';
  else if (motionMode === 'FAULT') modeAudit = '故障锁定中，必须先排障';

  return {
    safetyPhase,
    taskPhase,
    lastRejectedReason: null,
    modeAudit
  };
}
