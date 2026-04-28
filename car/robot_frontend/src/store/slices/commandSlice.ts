import { HISTORY_LIMIT, LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { safeNowIso } from '@/shared/utils';
import { applyInboundEventToState } from '@/store/inbound';
import { makeCommand, makeLog, makeTrace } from '@/store/defaults';
import { deriveRuntimeModel } from '@/store/helpers';
import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';
import { pushHistory } from '@/shared/utils';
import type { CommandLifecyclePhase, CommandStatus } from '@/types/robot';

function lifecyclePhaseFromCommandStatus(status: CommandStatus): CommandLifecyclePhase {
  if (status === 'timeout') return 'timed_out';
  if (status === 'sent') return 'client_sent';
  if (status === 'queued') return 'bridge_queued';
  if (['ack', 'accepted', 'applied'].includes(status)) return 'ros_accepted';
  if (status === 'completed') return 'business_completed';
  return 'failed';
}

export function createCommandSlice(
  set: Parameters<RobotStoreSlice<RobotStore>>[0],
): Pick<RobotStore, 'enqueueCommand' | 'markCommandSent' | 'markCommand' | 'applyInboundEvent' | 'recordTrace' | 'setRuntimeRejection'> {
  return {
    enqueueCommand: (id, type, summary, priority, dangerous) =>
      set((state) => ({
        commands: [
          makeCommand(id, type, summary, priority, dangerous),
          ...state.commands.map((item) =>
            type === 'teleop_cmd' && item.type === 'teleop_cmd' && (item.status === 'queued' || item.status === 'sent')
              ? {
                  ...item,
                  status: 'superseded' as const,
                  lifecycleStatus: 'superseded' as const,
                  lifecyclePhase: 'failed' as const,
                  lifecycleHistory: [
                    { phase: 'failed' as const, status: 'superseded' as const, timestamp: safeNowIso(), message: '被新的 teleop 命令替换' },
                    ...item.lifecycleHistory,
                  ].slice(0, 12),
                  updatedAt: safeNowIso(),
                  error: '被新的 teleop 命令替换',
                }
              : item,
          ),
        ].slice(0, 100),
      })),
    markCommandSent: (id) =>
      set((state) => ({
        commands: state.commands.map((item) => {
          if (item.id !== id) return item;
          const timestamp = safeNowIso();
          return {
            ...item,
            status: 'sent',
            lifecycleStatus: 'sent',
            lifecyclePhase: 'client_sent',
            lifecycleHistory: [
              { phase: 'client_sent' as const, status: 'sent' as const, timestamp, message: 'command sent by frontend transport' },
              ...item.lifecycleHistory,
            ].slice(0, 12),
            updatedAt: timestamp,
          };
        }),
      })),
    markCommand: (id, status, error) =>
      set((state) => {
        const nowIso = safeNowIso();
        const target = state.commands.find((item) => item.id === id);
        const lifecyclePhase = lifecyclePhaseFromCommandStatus(status);
        const ackLatencyMs =
          target && ['ack', 'accepted', 'applied', 'completed', 'rejected', 'denied', 'timeout', 'cancelled'].includes(status)
            ? Math.max(0, new Date(nowIso).getTime() - new Date(target.createdAt).getTime())
            : undefined;
        return {
          commands: state.commands.map((item) =>
            item.id === id
              ? {
                  ...item,
                  status,
                  lifecycleStatus: status,
                  lifecyclePhase,
                  lifecycleHistory: [
                    {
                      phase: lifecyclePhase,
                      status,
                      timestamp: nowIso,
                      message: error,
                    },
                    ...item.lifecycleHistory,
                  ].slice(0, 12),
                  updatedAt: nowIso,
                  error,
                  ackLatencyMs,
                }
              : item,
          ),
          history:
            ackLatencyMs !== undefined
              ? { ...state.history, ackLatency: pushHistory(state.history.ackLatency, ackLatencyMs, HISTORY_LIMIT) }
              : state.history,
        };
      }),
    applyInboundEvent: (event) =>
      set((state) => {
        const next = applyInboundEventToState(state, event);
        return {
          ...next,
          runtime: deriveRuntimeModel(next.connection, next.motion, next.power, next.fault, next.task, state.runtime.lastRejectedReason),
        };
      }),
    recordTrace: (direction, type, raw, verdict, note) =>
      set((state) => ({
        inspector: {
          trace: [makeTrace(direction, type, raw, verdict, note), ...state.inspector.trace].slice(0, 220),
        },
      })),
    setRuntimeRejection: (reason) =>
      set((state) => ({
        runtime: { ...deriveRuntimeModel(state.connection, state.motion, state.power, state.fault, state.task, reason), lastRejectedReason: reason },
        logs: reason ? [makeLog('WARN', 'SAFETY', '已拦截不安全或非法命令。', reason), ...state.logs].slice(0, MAX_LOGS) : state.logs,
      })),
  };
}
