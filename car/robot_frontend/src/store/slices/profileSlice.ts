import { LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { deepCloneParams } from '@/shared/utils';
import { makeLog } from '@/store/defaults';
import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';

export function createProfileSlice(set: Parameters<RobotStoreSlice<RobotStore>>[0]): Pick<RobotStore, 'setDraftParam' | 'resetDraftToApplied' | 'applyDraftParams' | 'applyProfile' | 'saveCurrentAsProfile'> {
  return {
    setDraftParam: (key, value) =>
      set((state) => ({
        profiles: {
          ...state.profiles,
          draft: { ...state.profiles.draft, [key]: value },
        },
      })),
    resetDraftToApplied: () =>
      set((state) => ({
        profiles: { ...state.profiles, draft: deepCloneParams(state.profiles.applied) },
      })),
    applyDraftParams: () =>
      set((state) => ({
        profiles: { ...state.profiles },
        logs: [makeLog('INFO', 'PARAM', '草稿参数已提交，等待 bridge ACK 与快照回写。'), ...state.logs].slice(0, MAX_LOGS),
      })),
    applyProfile: (profileName) =>
      set((state) => {
        const profile = state.profiles.profiles[profileName];
        if (!profile) return state;
        return {
          profiles: {
            ...state.profiles,
            activeProfileName: profileName,
            draft: deepCloneParams(profile),
          },
          logs: [makeLog('INFO', 'PARAM', `已加载参数草稿：${profileName}`), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
    saveCurrentAsProfile: (profileName) =>
      set((state) => ({
        profiles: {
          ...state.profiles,
          activeProfileName: profileName,
          profiles: { ...state.profiles.profiles, [profileName]: deepCloneParams(state.profiles.draft) },
        },
        logs: [makeLog('INFO', 'PARAM', `已保存参数配置：${profileName}`), ...state.logs].slice(0, MAX_LOGS),
      })),
  };
}
