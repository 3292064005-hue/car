import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';
import { makeLog } from '@/store/defaults';
import { LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { safeNowIso } from '@/shared/utils';

export function createLogSlice(set: Parameters<RobotStoreSlice<RobotStore>>[0]): Pick<RobotStore, 'pushLog'> {
  return {
    pushLog: (input) =>
      set((state) => ({
        logs: [makeLog(input.level, input.domain, input.message, input.details, input.timestamp ?? safeNowIso()), ...state.logs].slice(0, MAX_LOGS),
      })),
  };
}
