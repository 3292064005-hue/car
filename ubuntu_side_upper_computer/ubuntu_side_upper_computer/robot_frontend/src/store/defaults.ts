import {
  BRIDGE_CAPABILITIES,
  DEFAULT_DASHBOARD_LAYOUTS,
  DEFAULT_PANEL_VISIBILITY,
  DEFAULT_PARAMS,
  DEFAULT_WAYPOINTS,
  DEMO_READONLY,
  MJPEG_URL,
  PARAM_PRESETS,
  PROTOCOL_VERSION,
  SCHEMA_VERSION
} from '@/shared/constants';
import { deepCloneParams, safeNowIso, uuid } from '@/shared/utils';
import type {
  CommandRecord,
  CommandType,
  ConnectionState,
  DashboardLayouts,
  FaultState,
  HistoryState,
  InspectorRecord,
  InspectorState,
  LogDomain,
  LogItem,
  LogLevel,
  MotionState,
  PowerState,
  ReplayState,
  RuntimeState,
  StoredProfiles,
  TaskState,
  UiState,
  VisionState,
  VoiceState
} from '@/types/robot';
import type { RobotStoreData } from './model';

export const cloneLayouts = (layouts: DashboardLayouts): DashboardLayouts => JSON.parse(JSON.stringify(layouts)) as DashboardLayouts;

export const initialConnection: ConnectionState = {
  rosConnected: false,
  bridgeConnected: false,
  stm32Connected: false,
  videoConnected: false,
  voiceConnected: false,
  reconnecting: false,
  latencyMs: 0,
  heartbeatAgeMs: 0,
  lastHeartbeatAt: null,
  transportLabel: 'robot-bridge',
  transportType: 'mock',
  reconnectAttempts: 0,
  staleMotion: false,
  stalePower: false,
  staleVision: false,
  staleVoice: false,
  inboundRateHz: 0,
  outboundRateHz: 0,
  protocolVersion: PROTOCOL_VERSION,
  schemaVersion: SCHEMA_VERSION,
  capabilities: [...BRIDGE_CAPABILITIES],
  lastSnapshotVersion: null,
  lastTraceId: null,
  compatibilityMode: 'native-v4'
};

export const initialMotion: MotionState = {
  mode: 'BOOT',
  linearVelocity: 0,
  angularVelocity: 0,
  leftWheelSpeed: 0,
  rightWheelSpeed: 0,
  odomX: 0,
  odomY: 0,
  odomYaw: 0,
  isManualOverride: false,
  commandSource: 'unknown',
  lastUpdateAt: null
};

export const initialPower: PowerState = {
  batteryPercent: 100,
  batteryVoltage: 12.4,
  lowPowerWarning: false,
  charging: false,
  lastUpdateAt: null
};

export const initialVision: VisionState = {
  streamUrl: MJPEG_URL,
  targetType: null,
  targetOffsetX: 0,
  targetOffsetY: 0,
  qrcodeText: null,
  detectTimestamp: null,
  frameDrops: 0,
  trackingReady: false,
  lastUpdateAt: null,
  qrcodeHistory: []
};

export const initialVoice: VoiceState = {
  lastVoiceCommand: null,
  voiceConfidence: 0,
  speaking: false,
  lastSpeakText: null,
  wakeStatus: 'idle',
  lastUpdateAt: null,
  recentCommands: []
};

export const initialTask: TaskState = {
  patrolStatus: 'idle',
  currentWaypoint: null,
  progress: 0,
  totalPoints: 4,
  completedPoints: 0,
  trackEnabled: false,
  lastTaskEvent: null,
  actionName: null,
  actionPhase: 'idle',
  actionMessage: null,
  actionProgress: 0,
  commandId: null,
  commandType: null,
  lostTargetCount: 0,
  currentTargetType: null,
  waypoints: DEFAULT_WAYPOINTS
};

export const initialFault: FaultState = {
  level: 'info',
  code: null,
  message: null,
  safeStopActive: false,
  estopActive: false,
  timeoutStopActive: false,
  lastUpdateAt: null
};

export const initialProfiles: StoredProfiles = {
  activeProfileName: '演示标准',
  profiles: PARAM_PRESETS,
  applied: deepCloneParams(DEFAULT_PARAMS),
  draft: deepCloneParams(DEFAULT_PARAMS),
  configDigest: null,
  runtimeParamVersion: 1,
  lastParamApplyResult: null,
  lastTransaction: null
};

export const initialHistory: HistoryState = {
  latency: [],
  battery: [],
  leftWheel: [],
  rightWheel: [],
  frameDrops: [],
  ackLatency: []
};

export const initialUi: UiState = {
  logKeyword: '',
  logLevel: 'ALL',
  logDomain: 'ALL',
  demoReadonly: DEMO_READONLY,
  dashboardPreset: 'ops',
  panelVisibility: { ...DEFAULT_PANEL_VISIBILITY },
  dashboardLayouts: cloneLayouts(DEFAULT_DASHBOARD_LAYOUTS),
  activeBreakpoint: 'wide',
  lockedLayout: false
};

export const initialRuntime: RuntimeState = {
  safetyPhase: 'nominal',
  taskPhase: 'idle',
  lastRejectedReason: null,
  modeAudit: '系统待机'
};

export const initialInspector: InspectorState = {
  trace: []
};

export const initialReplay: ReplayState = {
  session: null,
  activeLogIndex: 0
};

export function makeLog(level: LogLevel, domain: LogDomain, message: string, details?: string, timestamp = safeNowIso()): LogItem {
  return {
    id: uuid('log'),
    timestamp,
    level,
    domain,
    message,
    details
  };
}

export function makeCommand(id: string, type: CommandType, summary: string, priority: CommandRecord['priority'], dangerous: boolean): CommandRecord {
  const now = safeNowIso();
  return {
    id,
    type,
    status: 'queued',
    summary,
    createdAt: now,
    updatedAt: now,
    priority,
    dangerous,
    requireAck: true,
    source: 'frontend'
  };
}

export function makeTrace(direction: InspectorRecord['direction'], type: string, raw: string, verdict: InspectorRecord['verdict'], note?: string): InspectorRecord {
  return {
    id: uuid('trace'),
    timestamp: safeNowIso(),
    direction,
    type,
    verdict,
    note,
    raw
  };
}

export function makeInitialStoreData(): RobotStoreData {
  return {
    connection: { ...initialConnection },
    motion: { ...initialMotion },
    power: { ...initialPower },
    vision: { ...initialVision, qrcodeHistory: [] },
    voice: { ...initialVoice, recentCommands: [] },
    task: { ...initialTask, waypoints: [...DEFAULT_WAYPOINTS] },
    fault: { ...initialFault },
    runtime: { ...initialRuntime },
    profiles: { ...initialProfiles, profiles: { ...PARAM_PRESETS }, applied: deepCloneParams(DEFAULT_PARAMS), draft: deepCloneParams(DEFAULT_PARAMS) },
    history: { ...initialHistory },
    inspector: { ...initialInspector, trace: [] },
    replay: { ...initialReplay },
    commands: [],
    logs: [makeLog('INFO', 'SYSTEM', '前端控制台 V4 已启动，等待 bridge 连接。')],
    ui: { ...initialUi, panelVisibility: { ...DEFAULT_PANEL_VISIBILITY }, dashboardLayouts: cloneLayouts(DEFAULT_DASHBOARD_LAYOUTS) }
  };
}
