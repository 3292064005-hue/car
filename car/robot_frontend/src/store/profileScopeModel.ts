import { BACKEND_AUTHORITATIVE_RUNTIME_PARAM_KEYS } from '@/shared/runtimeParamModel';
export type ProfileScope = 'runtime' | 'local';

export interface ParamProfileShape {
  maxLinearSpeed: number;
  maxAngularSpeed: number;
  teleopStep: number;
  trackOffsetDeadband: number;
  lowPowerThreshold: number;
  reconnectTimeoutMs: number;
}

export interface RuntimeProfileMetadata {
  activeProfileName?: string | null;
  committedProfileName?: string | null;
}

export interface RuntimeProfileReconcileInput {
  profiles: Record<string, ParamProfileShape>;
  profileScopes: Record<string, ProfileScope>;
  appliedProfile: ParamProfileShape;
  currentActiveProfileName: string;
  metadata?: RuntimeProfileMetadata | null;
}

export interface RuntimeProfileReconcileResult {
  profiles: Record<string, ParamProfileShape>;
  profileScopes: Record<string, ProfileScope>;
  activeProfileName: string;
  renamedLocalProfiles: Array<{ from: string; to: string }>;
}

/**
 * Validate one persisted profile scope value.
 *
 * Args:
 *   value: Arbitrary persisted value.
 *
 * Returns:
 *   ``'runtime'`` or ``'local'`` when the value is supported; otherwise
 *   ``undefined``.
 */
export function normalizeProfileScope(value: unknown): ProfileScope | undefined {
  return value === 'local' || value === 'runtime' ? value : undefined;
}

/**
 * Merge persisted profile-scope metadata with builtin preset defaults.
 *
 * Boundary behavior:
 *   Builtin preset names remain ``runtime`` unless explicit persisted metadata
 *   overrides them. Older persisted states without scope metadata keep
 *   user-created names as ``local`` so browser-only presets do not silently
 *   become backend runtime presets after migration.
 */
export function resolveProfileScopes(
  profileNames: string[],
  persistedScopes: unknown,
  builtinRuntimeProfileNames: string[],
): Record<string, ProfileScope> {
  const merged: Record<string, ProfileScope> = Object.fromEntries(
    builtinRuntimeProfileNames.map((name) => [name, 'runtime' as const]),
  );
  const rawScopes = persistedScopes && typeof persistedScopes === 'object'
    ? (persistedScopes as Record<string, unknown>)
    : {};
  for (const name of profileNames) {
    const normalized = normalizeProfileScope(rawScopes[name]);
    if (normalized) {
      merged[name] = normalized;
      continue;
    }
    if (!(name in merged)) {
      merged[name] = 'local';
    }
  }
  return merged;
}

/**
 * Produce a stable local alias when one browser-only preset collides with a
 * runtime preset name announced by the backend.
 */
export function nextLocalProfileAlias(
  requestedName: string,
  existingProfiles: Record<string, ParamProfileShape>,
): string {
  const base = `${String(requestedName || '').trim() || '未命名预设'}（本地）`;
  if (!(base in existingProfiles)) {
    return base;
  }
  let index = 2;
  while (`${base}-${index}` in existingProfiles) {
    index += 1;
  }
  return `${base}-${index}`;
}

/**
 * Reconcile backend-declared runtime profile metadata with browser-local preset
 * storage.
 *
 * Args:
 *   profiles: Existing frontend-visible profile map.
 *   profileScopes: Existing scope metadata for each profile name.
 *   appliedProfile: Runtime-applied parameter snapshot received from the
 *     backend.
 *   currentActiveProfileName: Current frontend selection.
 *   metadata: Optional backend metadata describing the authoritative runtime
 *     active/committed profile names.
 *
 * Returns:
 *   Updated profile map, scope map, the effective active profile name, and any
 *   browser-local rename operations caused by runtime/local name collisions.
 *
 * Boundary behavior:
 *   - Missing metadata never promotes a local preset to ``runtime``.
 *   - When the backend declares a runtime preset name that collides with an
 *     existing local preset, the local preset is preserved under a generated
 *     local alias and the runtime slot is refreshed with backend-applied values.
 */
export function reconcileRuntimeProfiles(input: RuntimeProfileReconcileInput): RuntimeProfileReconcileResult {
  const profiles: Record<string, ParamProfileShape> = { ...input.profiles };
  const profileScopes: Record<string, ProfileScope> = { ...input.profileScopes };
  const renamedLocalProfiles: Array<{ from: string; to: string }> = [];
  const explicitActiveProfileName = String(input.metadata?.activeProfileName ?? '').trim();
  const explicitCommittedProfileName = String(input.metadata?.committedProfileName ?? '').trim();

  const promoteRuntimeProfile = (profileName: string, profileValue: ParamProfileShape): void => {
    const normalizedName = String(profileName || '').trim();
    if (!normalizedName) {
      return;
    }
    if ((profileScopes[normalizedName] ?? 'runtime') === 'local' && normalizedName in profiles) {
      const alias = nextLocalProfileAlias(normalizedName, profiles);
      profiles[alias] = { ...profiles[normalizedName] };
      profileScopes[alias] = 'local';
      renamedLocalProfiles.push({ from: normalizedName, to: alias });
    }
    const existingProfile = profiles[normalizedName] ? { ...profiles[normalizedName] } : { ...profileValue };
    for (const key of BACKEND_AUTHORITATIVE_RUNTIME_PARAM_KEYS) {
      existingProfile[key] = profileValue[key];
    }
    profiles[normalizedName] = existingProfile;
    profileScopes[normalizedName] = 'runtime';
  };

  if (explicitActiveProfileName) {
    promoteRuntimeProfile(explicitActiveProfileName, input.appliedProfile);
  }
  if (explicitCommittedProfileName && explicitCommittedProfileName !== explicitActiveProfileName) {
    const committedWasLocal = (profileScopes[explicitCommittedProfileName] ?? 'runtime') === 'local' && explicitCommittedProfileName in profiles;
    if (committedWasLocal) {
      const alias = nextLocalProfileAlias(explicitCommittedProfileName, profiles);
      profiles[alias] = { ...profiles[explicitCommittedProfileName] };
      profileScopes[alias] = 'local';
      renamedLocalProfiles.push({ from: explicitCommittedProfileName, to: alias });
    }
    const committedProfile = committedWasLocal || !(explicitCommittedProfileName in profiles)
      ? { ...input.appliedProfile }
      : { ...profiles[explicitCommittedProfileName] };
    for (const key of BACKEND_AUTHORITATIVE_RUNTIME_PARAM_KEYS) {
      committedProfile[key] = input.appliedProfile[key];
    }
    profiles[explicitCommittedProfileName] = committedProfile;
    profileScopes[explicitCommittedProfileName] = 'runtime';
  }

  return {
    profiles,
    profileScopes,
    activeProfileName: explicitActiveProfileName || input.currentActiveProfileName,
    renamedLocalProfiles,
  };
}
