import { HISTORY_LIMIT, LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { deepCloneParams, pushHistory, uuid } from '@/shared/utils';
import { REPORT_SURFACE_CONTRACT } from '@/generated/reportSurfaceContract';
import { reportSurfaceEntrySchema } from '@/generated/bridgeContract';
import type { BridgeInboundEvent, CommandLifecyclePhase, CommandStatus, ReportSurfaceEntry, ReportsState } from '@/types/robot';
import type { RobotStoreData } from './model';
import { DEFAULT_PARAM_PROFILE_SCOPES, makeLog } from './defaults';
import { reconcileRuntimeProfiles } from './profileScopeModel';

type InboundProjection = Pick<
  RobotStoreData,
  'connection' | 'motion' | 'power' | 'vision' | 'voice' | 'task' | 'fault' | 'profiles' | 'history' | 'reports' | 'commands' | 'logs'
>;

type ReportContractKey = keyof typeof REPORT_SURFACE_CONTRACT;

const REPORT_STATE_KEYS = Object.keys(REPORT_SURFACE_CONTRACT) as ReportContractKey[];

function normalizeReportEntry(entry: unknown): ReportSurfaceEntry | undefined {
  const parsed = reportSurfaceEntrySchema.safeParse(entry);
  return parsed.success ? parsed.data : undefined;
}

function normalizeCapabilities(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function normalizeReportsState(current: ReportsState, incoming: Partial<ReportsState> | null | undefined): ReportsState {
  if (!incoming) {
    return current;
  }
  const nextReports = { ...current };
  for (const key of REPORT_STATE_KEYS) {
    const parsed = normalizeReportEntry(incoming[key]);
    nextReports[key] = parsed ?? current[key];
  }
  return nextReports;
}

function deriveConnectionBase(state: RobotStoreData, event: BridgeInboundEvent): Pick<InboundProjection, 'connection' | 'history'> {
  let connection = state.connection;
  let history = state.history;
  const connectionPayload =
    event.type === 'snapshot'
      ? event.payload.connection
      : event.type === 'heartbeat' || event.type === 'connection_state'
        ? event.payload
        : undefined;
  const compatibilityMode = 'native-v4';
  const nextCapabilities =
    normalizeCapabilities(event.capabilities).length > 0
      ? normalizeCapabilities(event.capabilities)
      : normalizeCapabilities(connectionPayload?.capabilities).length > 0
        ? normalizeCapabilities(connectionPayload?.capabilities)
        : normalizeCapabilities(connection.capabilities);

  connection = {
    ...connection,
    protocolVersion: event.protocolVersion,
    schemaVersion: event.schemaVersion,
    capabilities: nextCapabilities,
    lastTraceId: event.traceId ?? connection.lastTraceId,
    compatibilityMode,
  };

  if (event.type === 'heartbeat' || event.type === 'connection_state') {
    connection = {
      ...connection,
      ...event.payload,
      bridgeConnected: true,
      rosConnected: true,
      reconnecting: false,
      lastHeartbeatAt: event.ts,
      heartbeatAgeMs: 0,
    };
    history = {
      ...history,
      latency: pushHistory(history.latency, event.payload.latencyMs ?? state.connection.latencyMs, HISTORY_LIMIT),
    };
  }

  return { connection, history };
}

function reduceMotionSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'mode_state' && event.type !== 'chassis_state') {
    return;
  }
  projection.motion = { ...state.motion, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
  projection.history = {
    ...projection.history,
    leftWheel: pushHistory(projection.history.leftWheel, event.payload.leftWheelSpeed ?? state.motion.leftWheelSpeed, HISTORY_LIMIT),
    rightWheel: pushHistory(projection.history.rightWheel, event.payload.rightWheelSpeed ?? state.motion.rightWheelSpeed, HISTORY_LIMIT),
  };
}

function reducePowerSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'power_state') {
    return;
  }
  projection.power = { ...state.power, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
  projection.history = {
    ...projection.history,
    battery: pushHistory(projection.history.battery, event.payload.batteryPercent ?? state.power.batteryPercent, HISTORY_LIMIT),
  };
}

function reduceVisionSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type === 'vision_target') {
    projection.vision = { ...state.vision, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
    projection.history = {
      ...projection.history,
      frameDrops: pushHistory(projection.history.frameDrops, event.payload.frameDrops ?? state.vision.frameDrops, HISTORY_LIMIT),
    };
    return;
  }
  if (event.type === 'vision_qrcode') {
    projection.vision = {
      ...state.vision,
      ...event.payload,
      qrcodeHistory: event.payload.qrcodeText
        ? [{ id: uuid('qr'), ts: event.ts, label: event.payload.qrcodeText }, ...state.vision.qrcodeHistory].slice(0, 8)
        : state.vision.qrcodeHistory,
    };
  }
}

function reduceVoiceSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'voice_cmd') {
    return;
  }
  projection.voice = {
    ...state.voice,
    ...event.payload,
    lastUpdateAt: event.payload.lastUpdateAt ?? event.ts,
    recentCommands: event.payload.lastVoiceCommand
      ? [{ id: uuid('voice'), ts: event.ts, command: event.payload.lastVoiceCommand, confidence: event.payload.voiceConfidence ?? 0 }, ...state.voice.recentCommands].slice(0, 8)
      : state.voice.recentCommands,
  };
}

function reduceTaskSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'task_event') {
    return;
  }
  projection.task = { ...state.task, ...event.payload };
}

function reduceFaultSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'fault_event') {
    return;
  }
  projection.fault = { ...state.fault, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
}

function reduceLogSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'system_log') {
    return;
  }
  projection.logs = [event.payload, ...state.logs].slice(0, MAX_LOGS);
}


function lifecyclePhaseFromStatus(status: CommandStatus): CommandLifecyclePhase {
  if (status === 'queued') return 'bridge_queued';
  if (status === 'sent') return 'client_sent';
  if (status === 'ack' || status === 'accepted' || status === 'applied') return 'ros_accepted';
  if (status === 'completed') return 'business_completed';
  if (status === 'timeout') return 'timed_out';
  return 'failed';
}

function reduceCommandSlice(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'command_ack') {
    return;
  }
  const command = state.commands.find((item) => item.id === event.payload.commandId);
  const effectiveStatus = (event.payload.lifecycleStatus ?? event.payload.status) as CommandStatus;
  const lifecyclePhase = (event.payload.lifecyclePhase ?? lifecyclePhaseFromStatus(effectiveStatus)) as CommandLifecyclePhase;
  const ackLatencyMs =
    command && command.ackLatencyMs === undefined
      ? Math.max(0, new Date(event.ts).getTime() - new Date(command.createdAt).getTime())
      : command?.ackLatencyMs;
  projection.commands = state.commands.map((item) =>
    item.id === event.payload.commandId
      ? {
          ...item,
          status: effectiveStatus,
          lifecycleStatus: effectiveStatus,
          lifecyclePhase,
          lifecycleHistory: [
            {
              phase: lifecyclePhase,
              status: effectiveStatus,
              timestamp: event.ts,
              message: event.payload.message,
              detail: event.payload.detail,
            },
            ...item.lifecycleHistory,
          ].slice(0, 12),
          updatedAt: event.ts,
          error: event.payload.detail ?? event.payload.message,
          ackLatencyMs,
        }
      : item,
  );
  if (command && command.ackLatencyMs === undefined && ackLatencyMs !== undefined) {
    projection.history = { ...projection.history, ackLatency: pushHistory(projection.history.ackLatency, ackLatencyMs, HISTORY_LIMIT) };
  }
  if (event.payload.message) {
    const logLevel: 'INFO' | 'WARN' | 'ERROR' =
      effectiveStatus === 'accepted' || effectiveStatus === 'applied' || effectiveStatus === 'completed' || effectiveStatus === 'ack'
        ? 'INFO'
        : effectiveStatus === 'timeout'
          ? 'ERROR'
          : 'WARN';
    projection.logs = [
      makeLog(logLevel, 'BRIDGE', event.payload.message, event.payload.detail, event.ts),
      ...projection.logs,
    ].slice(0, MAX_LOGS);
  }
}

function reduceSnapshotSlices(state: RobotStoreData, event: BridgeInboundEvent, projection: InboundProjection): void {
  if (event.type !== 'snapshot') {
    return;
  }
  projection.connection = {
    ...projection.connection,
    ...(event.payload.connection ?? {}),
    lastSnapshotVersion: event.schemaVersion,
  };
  projection.motion = { ...state.motion, ...(event.payload.motion ?? {}) };
  projection.power = { ...state.power, ...(event.payload.power ?? {}) };
  projection.vision = { ...state.vision, ...(event.payload.vision ?? {}) };
  projection.voice = { ...state.voice, ...(event.payload.voice ?? {}) };
  projection.task = { ...state.task, ...(event.payload.task ?? {}) };
  projection.fault = { ...state.fault, ...(event.payload.fault ?? {}) };

  const nextApplied = deepCloneParams({ ...state.profiles.applied, ...(event.payload.params ?? {}) });
  const reconciliation = reconcileRuntimeProfiles({
    profiles: { ...state.profiles.profiles },
    profileScopes: { ...DEFAULT_PARAM_PROFILE_SCOPES, ...state.profiles.profileScopes },
    appliedProfile: nextApplied,
    currentActiveProfileName: state.profiles.activeProfileName,
    metadata: event.payload.paramMetadata ?? null,
  });
  const activeProfileName = reconciliation.activeProfileName;
  const nextProfiles = reconciliation.profiles;
  const nextProfileScopes = reconciliation.profileScopes;
  const hasLocalDraftEdits = JSON.stringify(state.profiles.draft) !== JSON.stringify(state.profiles.applied);

  projection.reports = normalizeReportsState(state.reports, event.payload.reports ?? undefined);
  projection.profiles = {
    ...state.profiles,
    activeProfileName,
    profiles: nextProfiles,
    profileScopes: nextProfileScopes,
    applied: nextApplied,
    draft: hasLocalDraftEdits ? deepCloneParams(state.profiles.draft) : deepCloneParams(nextApplied),
    configDigest: event.payload.paramMetadata?.configDigest ?? state.profiles.configDigest,
    runtimeParamVersion: event.payload.paramMetadata?.runtimeParamVersion ?? state.profiles.runtimeParamVersion,
    projectionState: event.payload.paramMetadata?.projectionState ?? state.profiles.projectionState,
    committedConfigDigest: event.payload.paramMetadata?.committedConfigDigest ?? state.profiles.committedConfigDigest,
    committedProfileName: event.payload.paramMetadata?.committedProfileName ?? state.profiles.committedProfileName,
    committedRuntimeParamVersion: event.payload.paramMetadata?.committedRuntimeParamVersion ?? state.profiles.committedRuntimeParamVersion,
    lastParamApplyResult: event.payload.paramMetadata?.lastParamApplyResult ?? state.profiles.lastParamApplyResult,
    lastTransaction: event.payload.paramMetadata?.lastTransaction ?? state.profiles.lastTransaction,
  };
  if (reconciliation.renamedLocalProfiles.length > 0) {
    const collisionMessage = reconciliation.renamedLocalProfiles
      .map(({ from, to }) => `运行时预设 ${from} 与本地预设重名，本地副本已自动保留为 ${to}`)
      .join('；');
    projection.logs = [
      makeLog('WARN', 'PARAM', collisionMessage, 'runtime_profile_name_collision_preserved_local_alias', event.ts),
      ...projection.logs,
    ].slice(0, MAX_LOGS);
  }
}

export function applyInboundEventToState(state: RobotStoreData, event: BridgeInboundEvent): InboundProjection {
  const base = deriveConnectionBase(state, event);
  const projection: InboundProjection = {
    connection: base.connection,
    motion: state.motion,
    power: state.power,
    vision: state.vision,
    voice: state.voice,
    task: state.task,
    fault: state.fault,
    profiles: state.profiles,
    history: base.history,
    reports: state.reports,
    commands: state.commands,
    logs: state.logs,
  };

  reduceMotionSlice(state, event, projection);
  reducePowerSlice(state, event, projection);
  reduceVisionSlice(state, event, projection);
  reduceVoiceSlice(state, event, projection);
  reduceTaskSlice(state, event, projection);
  reduceFaultSlice(state, event, projection);
  reduceLogSlice(state, event, projection);
  reduceCommandSlice(state, event, projection);
  reduceSnapshotSlices(state, event, projection);

  return projection;
}
