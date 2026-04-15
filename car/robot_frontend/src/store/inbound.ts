import { HISTORY_LIMIT, LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { deepCloneParams, pushHistory, uuid } from '@/shared/utils';
import { reportSurfaceEntrySchema } from '@/generated/bridgeContract';
import type { BridgeInboundEvent, ReportSurfaceEntry } from '@/types/robot';
import type { RobotStoreData } from './model';
import { DEFAULT_PARAM_PROFILE_SCOPES, makeLog } from './defaults';
import { reconcileRuntimeProfiles } from './profileScopeModel';

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

export function applyInboundEventToState(state: RobotStoreData, event: BridgeInboundEvent): Pick<RobotStoreData, 'connection' | 'motion' | 'power' | 'vision' | 'voice' | 'task' | 'fault' | 'profiles' | 'history' | 'reports' | 'commands' | 'logs'> {
  let connection = state.connection;
  let motion = state.motion;
  let power = state.power;
  let vision = state.vision;
  let voice = state.voice;
  let task = state.task;
  let fault = state.fault;
  let profiles = state.profiles;
  let history = state.history;
  let reports = state.reports;
  let commands = state.commands;
  let logs = state.logs;

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

  switch (event.type) {
    case 'heartbeat':
    case 'connection_state':
      connection = {
        ...connection,
        ...event.payload,
        bridgeConnected: true,
        rosConnected: true,
        reconnecting: false,
        lastHeartbeatAt: event.ts,
        heartbeatAgeMs: 0,
      };
      history = { ...history, latency: pushHistory(history.latency, event.payload.latencyMs ?? state.connection.latencyMs, HISTORY_LIMIT) };
      break;
    case 'mode_state':
    case 'chassis_state':
      motion = { ...state.motion, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
      history = {
        ...history,
        leftWheel: pushHistory(history.leftWheel, event.payload.leftWheelSpeed ?? state.motion.leftWheelSpeed, HISTORY_LIMIT),
        rightWheel: pushHistory(history.rightWheel, event.payload.rightWheelSpeed ?? state.motion.rightWheelSpeed, HISTORY_LIMIT),
      };
      break;
    case 'power_state':
      power = { ...state.power, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
      history = { ...history, battery: pushHistory(history.battery, event.payload.batteryPercent ?? state.power.batteryPercent, HISTORY_LIMIT) };
      break;
    case 'vision_target':
      vision = { ...state.vision, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
      history = { ...history, frameDrops: pushHistory(history.frameDrops, event.payload.frameDrops ?? state.vision.frameDrops, HISTORY_LIMIT) };
      break;
    case 'vision_qrcode':
      vision = {
        ...state.vision,
        ...event.payload,
        qrcodeHistory: event.payload.qrcodeText
          ? [{ id: uuid('qr'), ts: event.ts, label: event.payload.qrcodeText }, ...state.vision.qrcodeHistory].slice(0, 8)
          : state.vision.qrcodeHistory,
      };
      break;
    case 'voice_cmd':
      voice = {
        ...state.voice,
        ...event.payload,
        lastUpdateAt: event.payload.lastUpdateAt ?? event.ts,
        recentCommands: event.payload.lastVoiceCommand
          ? [{ id: uuid('voice'), ts: event.ts, command: event.payload.lastVoiceCommand, confidence: event.payload.voiceConfidence ?? 0 }, ...state.voice.recentCommands].slice(0, 8)
          : state.voice.recentCommands,
      };
      break;
    case 'task_event':
      task = { ...state.task, ...event.payload };
      break;
    case 'fault_event':
      fault = { ...state.fault, ...event.payload, lastUpdateAt: event.payload.lastUpdateAt ?? event.ts };
      break;
    case 'system_log':
      logs = [event.payload, ...state.logs].slice(0, MAX_LOGS);
      break;
    case 'command_ack': {
      const command = state.commands.find((item) => item.id === event.payload.commandId);
      const effectiveStatus = event.payload.lifecycleStatus ?? event.payload.status;
      const ackLatencyMs =
        command && command.ackLatencyMs === undefined
          ? Math.max(0, new Date(event.ts).getTime() - new Date(command.createdAt).getTime())
          : command?.ackLatencyMs;
      commands = state.commands.map((item) =>
        item.id === event.payload.commandId
          ? {
              ...item,
              status: effectiveStatus,
              updatedAt: event.ts,
              error: event.payload.detail ?? event.payload.message,
              ackLatencyMs,
            }
          : item,
      );
      if (command && command.ackLatencyMs === undefined && ackLatencyMs !== undefined) {
        history = { ...history, ackLatency: pushHistory(history.ackLatency, ackLatencyMs, HISTORY_LIMIT) };
      }
      if (event.payload.message) {
        const logLevel: 'INFO' | 'WARN' | 'ERROR' =
          effectiveStatus === 'accepted' || effectiveStatus === 'applied' || effectiveStatus === 'completed' || effectiveStatus === 'ack'
            ? 'INFO'
            : effectiveStatus === 'timeout'
              ? 'ERROR'
              : 'WARN';
        logs = [
          makeLog(logLevel, 'BRIDGE', event.payload.message, event.payload.detail, event.ts),
          ...logs,
        ].slice(0, MAX_LOGS);
      }
      break;
    }
    case 'snapshot': {
      connection = {
        ...connection,
        ...(event.payload.connection ?? {}),
        lastSnapshotVersion: event.schemaVersion,
      };
      motion = { ...state.motion, ...(event.payload.motion ?? {}) };
      power = { ...state.power, ...(event.payload.power ?? {}) };
      vision = { ...state.vision, ...(event.payload.vision ?? {}) };
      voice = { ...state.voice, ...(event.payload.voice ?? {}) };
      task = { ...state.task, ...(event.payload.task ?? {}) };
      fault = { ...state.fault, ...(event.payload.fault ?? {}) };
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
      reports = {
        controlSummary: normalizeReportEntry(event.payload.reports?.controlSummary) ?? state.reports.controlSummary,
        monitorSummary: normalizeReportEntry(event.payload.reports?.monitorSummary) ?? state.reports.monitorSummary,
        monitorDiagnostics: normalizeReportEntry(event.payload.reports?.monitorDiagnostics) ?? state.reports.monitorDiagnostics,
        localizationSummary: normalizeReportEntry(event.payload.reports?.localizationSummary) ?? state.reports.localizationSummary,
        hardwareInterfaceSummary: normalizeReportEntry(event.payload.reports?.hardwareInterfaceSummary) ?? state.reports.hardwareInterfaceSummary,
        navigationStatus: normalizeReportEntry(event.payload.reports?.navigationStatus) ?? state.reports.navigationStatus,
        voiceIngressHealth: normalizeReportEntry(event.payload.reports?.voiceIngressHealth) ?? state.reports.voiceIngressHealth,
        navigationPath: normalizeReportEntry(event.payload.reports?.navigationPath) ?? state.reports.navigationPath,
        runtimeSupervision: normalizeReportEntry(event.payload.reports?.runtimeSupervision) ?? state.reports.runtimeSupervision,
      };
      profiles = {
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
        const renameLogs = reconciliation.renamedLocalProfiles.map(({ from, to }) =>
          makeLog('WARN', 'PARAM', `本地参数预设 ${from} 与运行时预设重名，已自动保留为 ${to}。`, undefined, event.ts),
        );
        logs = [...renameLogs, ...state.logs].slice(0, MAX_LOGS);
      } else {
        logs = state.logs;
      }
      logs = event.payload.logs ? [...event.payload.logs, ...logs].slice(0, MAX_LOGS) : logs;
      break;
    }
  }

  return {
    connection,
    motion,
    power,
    vision,
    voice,
    task,
    fault,
    profiles,
    history,
    reports,
    commands,
    logs,
  };
}
