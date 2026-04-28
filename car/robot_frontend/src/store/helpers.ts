import { canTransitionMode, deriveRuntimeState } from '@/machines/stateMachine';
import { COMMAND_TIMEOUT_MS, STALE_THRESHOLDS_MS } from '@/shared/constants';
import { pushHistory, safeNowIso } from '@/shared/utils';
import type {
  CommandRecord,
  ConnectionState,
  DashboardBreakpoint,
  DashboardLayouts,
  DashboardPreset,
  FaultState,
  HistoryState,
  MotionState,
  PanelId,
  PowerState,
  RuntimeState,
  TaskState
} from '@/types/robot';

export function deriveRuntimeModel(connection: ConnectionState, motion: MotionState, power: PowerState, fault: FaultState, task: TaskState, lastRejectedReason: string | null): RuntimeState {
  return {
    ...deriveRuntimeState({ motionMode: motion.mode, connection, power, fault, task }),
    lastRejectedReason
  };
}

export function inferBreakpoint(width: number): DashboardBreakpoint {
  if (width < 900) return 'compact';
  if (width < 1320) return 'normal';
  return 'wide';
}

export function mergeLayoutVisibility(layouts: DashboardLayouts, panelVisibility: Record<PanelId, boolean>, preset: DashboardPreset): Record<PanelId, boolean> {
  const next = { ...panelVisibility };
  (Object.keys(next) as PanelId[]).forEach((panelId) => {
    next[panelId] = layouts[preset].some((item) => item.id === panelId) ? next[panelId] : false;
  });
  return next;
}

export function applyCommandTimeouts(commands: CommandRecord[], timeoutBoundary: number): CommandRecord[] {
  const now = Date.now();
  return commands.map((item) => {
    if (item.status !== 'queued' && item.status !== 'sent') return item;
    const created = new Date(item.createdAt).getTime();
    if (now - created <= timeoutBoundary) return item;
    const timestamp = safeNowIso();
    return {
      ...item,
      status: 'timeout',
      lifecycleStatus: 'timeout',
      lifecyclePhase: 'timed_out',
      lifecycleHistory: [
        { phase: 'timed_out' as const, status: 'timeout' as const, timestamp, message: '命令等待 ACK 超时' },
        ...item.lifecycleHistory,
      ].slice(0, 12),
      updatedAt: timestamp,
      error: '命令等待 ACK 超时',
    };
  });
}

export function buildRuntimeTick(connection: ConnectionState, motion: MotionState, power: PowerState, visionTimestamp: string | null, voiceTimestamp: string | null, traceTimestamps: Array<{ direction: 'in' | 'out' | 'rejected'; timestamp: string }>, reconnectTimeoutMs: number, commands: CommandRecord[]): { connection: ConnectionState; commands: CommandRecord[] } {
  const now = Date.now();
  const lastHeartbeat = connection.lastHeartbeatAt ? new Date(connection.lastHeartbeatAt).getTime() : now;
  const heartbeatAgeMs = Math.max(0, now - lastHeartbeat);
  const markStale = (ts: string | null, threshold: number) => {
    if (!ts) return true;
    const parsed = new Date(ts).getTime();
    return Number.isNaN(parsed) ? true : now - parsed > threshold;
  };
  const timeoutBoundary = Math.max(COMMAND_TIMEOUT_MS, reconnectTimeoutMs);
  const nextCommands = applyCommandTimeouts(commands, timeoutBoundary);
  const traceRecent = traceTimestamps.filter((item) => now - new Date(item.timestamp).getTime() <= 1000);
  const inboundRateHz = traceRecent.filter((item) => item.direction === 'in').length;
  const outboundRateHz = traceRecent.filter((item) => item.direction === 'out').length;
  return {
    connection: {
      ...connection,
      heartbeatAgeMs,
      staleMotion: markStale(motion.lastUpdateAt, STALE_THRESHOLDS_MS.motion),
      stalePower: markStale(power.lastUpdateAt, STALE_THRESHOLDS_MS.power),
      staleVision: markStale(visionTimestamp, STALE_THRESHOLDS_MS.vision),
      staleVoice: markStale(voiceTimestamp, STALE_THRESHOLDS_MS.voice),
      reconnecting: heartbeatAgeMs > Math.max(STALE_THRESHOLDS_MS.heartbeat, reconnectTimeoutMs) || !connection.bridgeConnected,
      inboundRateHz,
      outboundRateHz
    },
    commands: nextCommands,
  };
}

export { canTransitionMode, pushHistory };
