import {
  RUNTIME_PARAM_BACKEND_AUTHORITATIVE_KEYS,
  RUNTIME_PARAM_FIELD_SCOPES,
  RUNTIME_PARAM_FRONTEND_LOCAL_KEYS,
  RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE,
  RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL,
} from '@/generated/bridgeContract';
import type { ParamProfile } from '@/types/robot';

export type RuntimeParamKey = keyof ParamProfile;
export type RuntimeParamScope = typeof RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE | typeof RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL;
export type RuntimeParamPatch = Partial<ParamProfile>;

export const BACKEND_AUTHORITATIVE_RUNTIME_PARAM_KEYS = [...RUNTIME_PARAM_BACKEND_AUTHORITATIVE_KEYS] as RuntimeParamKey[];
export const FRONTEND_LOCAL_RUNTIME_PARAM_KEYS = [...RUNTIME_PARAM_FRONTEND_LOCAL_KEYS] as RuntimeParamKey[];

export interface RuntimeParamPatchSplit {
  authoritativePatch: RuntimeParamPatch;
  frontendLocalPatch: RuntimeParamPatch;
  authoritativeKeys: RuntimeParamKey[];
  frontendLocalKeys: RuntimeParamKey[];
}

/**
 * Return the declared ownership scope for one runtime parameter field.
 */
export function runtimeParamScope(key: RuntimeParamKey): RuntimeParamScope {
  return (RUNTIME_PARAM_FIELD_SCOPES[key] ?? RUNTIME_PARAM_SCOPE_BACKEND_AUTHORITATIVE) as RuntimeParamScope;
}

/**
 * Split one patch into backend-authoritative and browser-local subsets.
 */
export function splitRuntimeParamPatch(patch: RuntimeParamPatch): RuntimeParamPatchSplit {
  const authoritativePatch: RuntimeParamPatch = {};
  const frontendLocalPatch: RuntimeParamPatch = {};
  const authoritativeKeys: RuntimeParamKey[] = [];
  const frontendLocalKeys: RuntimeParamKey[] = [];
  for (const key of Object.keys(patch) as RuntimeParamKey[]) {
    const value = patch[key];
    if (value === undefined) continue;
    if (runtimeParamScope(key) === RUNTIME_PARAM_SCOPE_FRONTEND_LOCAL) {
      frontendLocalPatch[key] = value;
      frontendLocalKeys.push(key);
      continue;
    }
    authoritativePatch[key] = value;
    authoritativeKeys.push(key);
  }
  return { authoritativePatch, frontendLocalPatch, authoritativeKeys, frontendLocalKeys };
}

/**
 * Build one diff patch from applied -> draft and classify it by ownership.
 */
export function diffRuntimeParamPatch(applied: ParamProfile, draft: ParamProfile): RuntimeParamPatchSplit {
  const patch: RuntimeParamPatch = {};
  for (const key of Object.keys(draft) as RuntimeParamKey[]) {
    if (draft[key] !== applied[key]) {
      patch[key] = draft[key];
    }
  }
  return splitRuntimeParamPatch(patch);
}
