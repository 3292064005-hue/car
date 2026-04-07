import { LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { safeNowIso } from '@/shared/utils';
import { makeLog } from '@/store/defaults';
import { buildRuntimeTick, deriveRuntimeModel } from '@/store/helpers';
import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';

export function createConnectionSlice(set: Parameters<RobotStoreSlice<RobotStore>>[0]): Pick<RobotStore, 'setTransportInfo' | 'markBridgeOpen' | 'markBridgeClosed' | 'tickRuntime'> {
  return {
    setTransportInfo: (type, label) =>
      set((state) => ({
        connection: { ...state.connection, transportType: type, transportLabel: label },
      })),
    markBridgeOpen: () =>
      set((state) => {
        const connection = {
          ...state.connection,
          bridgeConnected: true,
          rosConnected: true,
          reconnecting: false,
          lastHeartbeatAt: safeNowIso(),
          heartbeatAgeMs: 0,
        };
        return {
          connection,
          runtime: deriveRuntimeModel(connection, state.motion, state.power, state.fault, state.task, state.runtime.lastRejectedReason),
          logs: [makeLog('INFO', 'BRIDGE', '桥接层已连接。'), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
    markBridgeClosed: () =>
      set((state) => {
        const connection = {
          ...state.connection,
          bridgeConnected: false,
          rosConnected: false,
          reconnecting: true,
          reconnectAttempts: state.connection.reconnectAttempts + 1,
        };
        return {
          connection,
          runtime: deriveRuntimeModel(connection, state.motion, state.power, state.fault, state.task, state.runtime.lastRejectedReason),
          logs: [makeLog('WARN', 'BRIDGE', '桥接层已断开，进入重连状态。'), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
    tickRuntime: () =>
      set((state) => {
        const tick = buildRuntimeTick(
          state.connection,
          state.motion,
          state.power,
          state.vision.lastUpdateAt ?? state.vision.detectTimestamp,
          state.voice.lastUpdateAt,
          state.inspector.trace,
          state.profiles.applied.reconnectTimeoutMs,
          state.commands,
        );
        return {
          connection: tick.connection,
          commands: tick.commands,
          runtime: deriveRuntimeModel(tick.connection, state.motion, state.power, state.fault, state.task, state.runtime.lastRejectedReason),
        };
      }),
  };
}
