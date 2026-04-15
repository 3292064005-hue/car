import { LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { deepCloneParams } from '@/shared/utils';
import { diffRuntimeParamPatch } from '@/shared/runtimeParamModel';
import { makeLog } from '@/store/defaults';
import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';

/**
 * Frontend profile editing stays browser-local until the operator explicitly
 * applies a runtime draft/profile through the bridge. This slice therefore keeps
 * local presets separate from runtime-backed preset intent by recording a scope
 * per preset name.
 */
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
      set((state) => {
        const split = diffRuntimeParamPatch(state.profiles.applied, state.profiles.draft);
        const nextApplied = {
          ...state.profiles.applied,
          ...split.frontendLocalPatch,
        };
        let message = '草稿参数已提交，等待 bridge ACK 与快照回写。';
        if (split.authoritativeKeys.length === 0 && split.frontendLocalKeys.length > 0) {
          message = `浏览器本地参数已应用：${split.frontendLocalKeys.join(', ')}`;
        } else if (split.authoritativeKeys.length > 0 && split.frontendLocalKeys.length > 0) {
          message = `本地参数已写入浏览器（${split.frontendLocalKeys.join(', ')}），权威字段等待 bridge ACK。`;
        }
        return {
          profiles: { ...state.profiles, applied: deepCloneParams(nextApplied) },
          logs: [makeLog('INFO', 'PARAM', message), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
    applyProfile: (profileName) =>
      set((state) => {
        const profile = state.profiles.profiles[profileName];
        if (!profile) return state;
        const scope = state.profiles.profileScopes[profileName] ?? 'runtime';
        return {
          profiles: {
            ...state.profiles,
            activeProfileName: profileName,
            draft: deepCloneParams(profile),
          },
          logs: [makeLog('INFO', 'PARAM', `已加载${scope === 'local' ? '本地' : '运行时'}参数预设：${profileName}`), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
    saveCurrentAsProfile: (profileName) =>
      set((state) => {
        const normalizedName = String(profileName ?? '').trim();
        if (!normalizedName) {
          return {
            profiles: { ...state.profiles },
            logs: [makeLog('WARN', 'PARAM', '本地参数预设名称不能为空。'), ...state.logs].slice(0, MAX_LOGS),
          };
        }
        const existingScope = state.profiles.profileScopes[normalizedName];
        if (existingScope === 'runtime') {
          return {
            profiles: { ...state.profiles },
            logs: [makeLog('WARN', 'PARAM', `名称 ${normalizedName} 已被运行时预设占用，请改用其他本地预设名称。`), ...state.logs].slice(0, MAX_LOGS),
          };
        }
        return {
          profiles: {
            ...state.profiles,
            activeProfileName: normalizedName,
            profiles: { ...state.profiles.profiles, [normalizedName]: deepCloneParams(state.profiles.draft) },
            profileScopes: { ...state.profiles.profileScopes, [normalizedName]: 'local' },
          },
          logs: [makeLog('INFO', 'PARAM', `已保存本地参数预设：${normalizedName}`), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
  };
}
