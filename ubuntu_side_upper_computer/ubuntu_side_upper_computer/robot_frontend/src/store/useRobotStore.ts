import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { RobotMode } from '@/types/robot';
import { canTransitionMode } from '@/store/helpers';
import { makeInitialStoreData } from '@/store/defaults';
import type { RobotStore } from '@/store/model';
import { createConnectionSlice } from '@/store/slices/connectionSlice';
import { createLogSlice } from '@/store/slices/logSlice';
import { createCommandSlice } from '@/store/slices/commandSlice';
import { createUiSlice } from '@/store/slices/uiSlice';
import { createProfileSlice } from '@/store/slices/profileSlice';
import { createReplaySlice } from '@/store/slices/replaySlice';
import { createExportSlice } from '@/store/slices/exportSlice';

const initialState = makeInitialStoreData();

function migratePersistedState(persisted: unknown): { profiles: RobotStore['profiles']; ui: RobotStore['ui'] } {
  if (!persisted || typeof persisted !== 'object') {
    return { profiles: initialState.profiles, ui: initialState.ui };
  }
  const state = persisted as Partial<RobotStore>;
  const profiles = state.profiles
    ? {
        ...initialState.profiles,
        ...state.profiles,
        profiles: { ...initialState.profiles.profiles, ...(state.profiles.profiles ?? {}) },
        applied: { ...initialState.profiles.applied, ...(state.profiles.applied ?? {}) },
        draft: { ...initialState.profiles.draft, ...(state.profiles.draft ?? {}) },
      }
    : initialState.profiles;
  const ui = state.ui
    ? {
        ...initialState.ui,
        ...state.ui,
        panelVisibility: { ...initialState.ui.panelVisibility, ...(state.ui.panelVisibility ?? {}) },
        dashboardLayouts: state.ui.dashboardLayouts ?? initialState.ui.dashboardLayouts,
      }
    : initialState.ui;
  return { profiles, ui };
}

export const useRobotStore = create<RobotStore>()(
  persist(
    (set, get) => ({
      ...initialState,
      ...createConnectionSlice(set),
      ...createLogSlice(set),
      ...createCommandSlice(set),
      ...createUiSlice(set),
      ...createProfileSlice(set),
      ...createReplaySlice(set),
      ...createExportSlice(get),
    }),
    {
      name: 'robot-console-v4',
      version: 2,
      migrate: (persistedState) => migratePersistedState(persistedState),
      partialize: (state) => ({
        profiles: state.profiles,
        ui: state.ui,
      }),
    },
  ),
);

export function validateModeTransition(mode: RobotMode): { allowed: boolean; reason?: string } {
  const state = useRobotStore.getState();
  return canTransitionMode({ currentMode: state.motion.mode, targetMode: mode, fault: state.fault, connection: state.connection, power: state.power });
}
