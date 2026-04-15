import { DEFAULT_PARAM_PROFILE_SCOPES, makeInitialStoreData } from '@/store/defaults';
import { resolveProfileScopes } from '@/store/profileScopeModel';
import type { RobotStore } from '@/store/model';

const initialState = makeInitialStoreData();

/**
 * Normalize persisted profile/UI state loaded by Zustand ``persist``.
 *
 * Args:
 *   persisted: Raw persisted state from browser storage.
 *
 * Returns:
 *   Normalized subset containing only the persisted ``profiles`` and ``ui``
 *   slices expected by the runtime store.
 *
 * Boundary behavior:
 *   Missing or malformed input falls back to the repository defaults. Legacy
 *   persisted profile sets without explicit scope metadata keep builtin preset
 *   names as ``runtime`` and browser-created names as ``local``.
 */
export function migratePersistedStoreState(persisted: unknown): { profiles: RobotStore['profiles']; ui: RobotStore['ui'] } {
  if (!persisted || typeof persisted !== 'object') {
    return { profiles: initialState.profiles, ui: initialState.ui };
  }
  const state = persisted as Partial<RobotStore>;
  const profiles = state.profiles
    ? (() => {
        const mergedProfiles = { ...initialState.profiles.profiles, ...(state.profiles.profiles ?? {}) };
        return {
          ...initialState.profiles,
          ...state.profiles,
          profiles: mergedProfiles,
          profileScopes: resolveProfileScopes(Object.keys(mergedProfiles), state.profiles.profileScopes, Object.keys(DEFAULT_PARAM_PROFILE_SCOPES)),
          applied: { ...initialState.profiles.applied, ...(state.profiles.applied ?? {}) },
          draft: { ...initialState.profiles.draft, ...(state.profiles.draft ?? {}) },
        };
      })()
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
