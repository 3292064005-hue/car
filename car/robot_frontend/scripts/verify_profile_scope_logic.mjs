import { loadTsModule } from './load-ts-module.mjs';

const { resolveProfileScopes, reconcileRuntimeProfiles } = loadTsModule('./src/store/profileScopeModel.ts');
const { migratePersistedStoreState } = loadTsModule('./src/store/profilePersistenceModel.ts');
const { applyInboundEventToState } = loadTsModule('./src/store/inbound.ts');
const { makeInitialStoreData } = loadTsModule('./src/store/defaults.ts');

const builtinScopes = resolveProfileScopes(['演示标准', '自定义一'], undefined, ['演示标准']);
if (builtinScopes['演示标准'] !== 'runtime') {
  throw new Error('builtin runtime preset lost runtime scope');
}
if (builtinScopes['自定义一'] !== 'local') {
  throw new Error('legacy user preset did not migrate to local scope');
}

const noMetadata = reconcileRuntimeProfiles({
  profiles: {
    本地调试: {
      maxLinearSpeed: 0.1,
      maxAngularSpeed: 0.1,
      teleopStep: 0.01,
      trackOffsetDeadband: 0.02,
      lowPowerThreshold: 20,
      reconnectTimeoutMs: 1000,
    },
  },
  profileScopes: { 本地调试: 'local' },
  appliedProfile: {
    maxLinearSpeed: 0.2,
    maxAngularSpeed: 0.2,
    teleopStep: 0.02,
    trackOffsetDeadband: 0.03,
    lowPowerThreshold: 25,
    reconnectTimeoutMs: 2000,
  },
  currentActiveProfileName: '本地调试',
  metadata: {},
});
if (noMetadata.profileScopes['本地调试'] !== 'local') {
  throw new Error('missing metadata promoted a local preset to runtime');
}

const collision = reconcileRuntimeProfiles({
  profiles: {
    巡检默认: {
      maxLinearSpeed: 0.15,
      maxAngularSpeed: 0.15,
      teleopStep: 0.03,
      trackOffsetDeadband: 0.03,
      lowPowerThreshold: 18,
      reconnectTimeoutMs: 1500,
    },
  },
  profileScopes: { 巡检默认: 'local' },
  appliedProfile: {
    maxLinearSpeed: 0.25,
    maxAngularSpeed: 0.5,
    teleopStep: 0.05,
    trackOffsetDeadband: 0.1,
    lowPowerThreshold: 15,
    reconnectTimeoutMs: 3000,
  },
  currentActiveProfileName: '巡检默认',
  metadata: { activeProfileName: '巡检默认' },
});
if (collision.profileScopes['巡检默认'] !== 'runtime') {
  throw new Error('runtime preset collision did not keep runtime slot authoritative');
}
if (!collision.renamedLocalProfiles.length) {
  throw new Error('runtime/local collision did not preserve the local preset under an alias');
}
const alias = collision.renamedLocalProfiles[0].to;
if (collision.profileScopes[alias] !== 'local') {
  throw new Error('renamed collision alias lost local scope');
}

const migrated = migratePersistedStoreState({
  profiles: {
    profiles: {
      巡检默认: {
        maxLinearSpeed: 0.12,
        maxAngularSpeed: 0.24,
        teleopStep: 0.02,
        trackOffsetDeadband: 0.03,
        lowPowerThreshold: 17,
        reconnectTimeoutMs: 1600,
      },
    },
    applied: {
      maxLinearSpeed: 0.12,
      maxAngularSpeed: 0.24,
      teleopStep: 0.02,
      trackOffsetDeadband: 0.03,
      lowPowerThreshold: 17,
      reconnectTimeoutMs: 1600,
    },
    draft: {
      maxLinearSpeed: 0.12,
      maxAngularSpeed: 0.24,
      teleopStep: 0.02,
      trackOffsetDeadband: 0.03,
      lowPowerThreshold: 17,
      reconnectTimeoutMs: 1600,
    },
    activeProfileName: '巡检默认',
  },
  ui: {},
});
if (migrated.profiles.profileScopes['巡检默认'] !== 'local') {
  throw new Error('persist migration did not classify legacy user preset as local');
}

const initial = makeInitialStoreData();
const mergedState = {
  ...initial,
  profiles: migrated.profiles,
  ui: migrated.ui,
};

const snapshotEvent = {
  type: 'snapshot',
  protocolVersion: '4.0.0',
  schemaVersion: 4,
  ts: '2026-04-11T00:00:00Z',
  traceId: 'trace-profile-snapshot',
  capabilities: {},
  payload: {
    connection: { bridgeConnected: true, rosConnected: true, reconnecting: false },
    params: {
      maxLinearSpeed: 0.3,
      maxAngularSpeed: 0.5,
      teleopStep: 0.05,
      trackOffsetDeadband: 0.1,
      lowPowerThreshold: 15,
      reconnectTimeoutMs: 3000,
    },
    paramMetadata: {
      activeProfileName: '巡检默认',
      committedProfileName: '巡检默认',
      configDigest: 'digest-a',
      runtimeParamVersion: 7,
      projectionState: 'projected',
      committedConfigDigest: 'digest-a',
      committedRuntimeParamVersion: 7,
      lastParamApplyResult: 'applied',
      lastTransaction: 'tx-1',
    },
    reports: {},
    logs: [],
  },
};

const updated = applyInboundEventToState(mergedState, snapshotEvent);
if (updated.profiles.profileScopes['巡检默认'] !== 'runtime') {
  throw new Error('snapshot reconciliation did not reserve runtime preset scope');
}
const localAliases = Object.entries(updated.profiles.profileScopes).filter(([, scope]) => scope === 'local');
if (!localAliases.some(([name]) => String(name).startsWith('巡检默认（本地）'))) {
  throw new Error('snapshot reconciliation did not preserve conflicting local preset under local alias');
}
if (!updated.logs.some((entry) => entry.message.includes('自动保留为'))) {
  throw new Error('snapshot reconciliation did not emit collision log');
}

const followUpState = { ...mergedState, ...updated, logs: updated.logs };
const noMetadataEvent = {
  ...snapshotEvent,
  traceId: 'trace-profile-snapshot-2',
  payload: {
    ...snapshotEvent.payload,
    paramMetadata: {},
    params: {
      maxLinearSpeed: 0.31,
      maxAngularSpeed: 0.52,
      teleopStep: 0.05,
      trackOffsetDeadband: 0.1,
      lowPowerThreshold: 15,
      reconnectTimeoutMs: 3000,
    },
  },
};
const noMetadataUpdated = applyInboundEventToState(followUpState, noMetadataEvent);
if (noMetadataUpdated.profiles.profileScopes['巡检默认（本地）'] !== 'local') {
  throw new Error('metadata-free snapshot should not promote the preserved local alias');
}

console.log('profile scope logic + integration ok');
