import { HISTORY_LIMIT, LOG_LIMIT as MAX_LOGS } from '@/shared/constants';
import { deepCloneParams, pushHistory, uuid } from '@/shared/utils';
import type { BridgeInboundEvent } from '@/types/robot';
import type { RobotStoreData } from './model';
import { makeLog } from './defaults';

export function applyInboundEventToState(state: RobotStoreData, event: BridgeInboundEvent): Pick<RobotStoreData, 'connection' | 'motion' | 'power' | 'vision' | 'voice' | 'task' | 'fault' | 'profiles' | 'history' | 'commands' | 'logs'> {
  let connection = state.connection;
  let motion = state.motion;
  let power = state.power;
  let vision = state.vision;
  let voice = state.voice;
  let task = state.task;
  let fault = state.fault;
  let profiles = state.profiles;
  let history = state.history;
  let commands = state.commands;
  let logs = state.logs;

  const compatibilityMode = event.protocolVersion.startsWith('4') ? 'native-v4' : event.protocolVersion.startsWith('3') ? 'legacy-v3' : 'legacy-v2';

  connection = {
    ...connection,
    protocolVersion: event.protocolVersion,
    schemaVersion: event.schemaVersion,
    capabilities: event.capabilities ?? connection.capabilities,
    lastTraceId: event.traceId ?? connection.lastTraceId,
    compatibilityMode,
  };

  switch (event.type) {
    case 'heartbeat':
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
      const activeProfileName = event.payload.paramMetadata?.activeProfileName ?? state.profiles.activeProfileName;
      const nextProfiles = { ...state.profiles.profiles };
      const hasLocalDraftEdits = JSON.stringify(state.profiles.draft) !== JSON.stringify(state.profiles.applied);
      if (activeProfileName && !(activeProfileName in nextProfiles)) {
        nextProfiles[activeProfileName] = deepCloneParams(nextApplied);
      }
      profiles = {
        ...state.profiles,
        activeProfileName,
        profiles: nextProfiles,
        applied: nextApplied,
        draft: hasLocalDraftEdits ? deepCloneParams(state.profiles.draft) : deepCloneParams(nextApplied),
        configDigest: event.payload.paramMetadata?.configDigest ?? state.profiles.configDigest,
        runtimeParamVersion: event.payload.paramMetadata?.runtimeParamVersion ?? state.profiles.runtimeParamVersion,
        lastParamApplyResult: event.payload.paramMetadata?.lastParamApplyResult ?? state.profiles.lastParamApplyResult,
        lastTransaction: event.payload.paramMetadata?.lastTransaction ?? state.profiles.lastTransaction,
      };
      logs = event.payload.logs ? [...event.payload.logs, ...state.logs].slice(0, MAX_LOGS) : state.logs;
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
    commands,
    logs,
  };
}
