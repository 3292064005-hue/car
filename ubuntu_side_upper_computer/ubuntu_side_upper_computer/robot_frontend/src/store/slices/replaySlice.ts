import { LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { initialReplay, makeLog } from '@/store/defaults';
import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';

export function createReplaySlice(set: Parameters<RobotStoreSlice<RobotStore>>[0]): Pick<RobotStore, 'loadReplaySession' | 'setReplayIndex' | 'clearReplaySession'> {
  return {
    loadReplaySession: (session) =>
      set((state) => ({
        replay: { session, activeLogIndex: 0 },
        logs: [makeLog('INFO', 'REPLAY', `已加载回放会话：${session.sourceName || '未知来源'}`), ...state.logs].slice(0, MAX_LOGS),
      })),
    setReplayIndex: (index) =>
      set((state) => ({
        replay: { ...state.replay, activeLogIndex: Math.max(0, Math.min(index, Math.max(0, (state.replay.session?.logs.length ?? 1) - 1))) },
      })),
    clearReplaySession: () =>
      set((state) => ({
        replay: initialReplay,
        logs: [makeLog('INFO', 'REPLAY', '已清空回放会话。'), ...state.logs].slice(0, MAX_LOGS),
      })),
  };
}
