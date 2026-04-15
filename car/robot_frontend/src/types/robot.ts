import type {
  GeneratedBridgeInboundPayloadMap,
  GeneratedBridgeOutboundPayloadMap,
  GeneratedCommandType,
  GeneratedInboundEventType,
  GeneratedParamProfile,
  GeneratedRobotSnapshot,
  GeneratedReportSurfaceEntry,
  GeneratedReportsStatePayload,
  GeneratedRuntimeParamApplyResult,
  GeneratedRuntimeParamConsumerStatus,
  GeneratedRuntimeParamTransactionState
} from '@/generated/bridgeContract';

export type RobotMode = 'BOOT' | 'IDLE' | 'MANUAL' | 'PATROL' | 'TRACK' | 'SAFE_STOP' | 'FAULT';
export type FaultLevel = 'info' | 'warning' | 'critical';
export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL';
export type LogDomain = 'SYSTEM' | 'BRIDGE' | 'CONTROL' | 'VISION' | 'VOICE' | 'TASK' | 'SAFETY' | 'PARAM' | 'REPLAY' | 'INSPECTOR' | 'REPORT';
export type CommandType = GeneratedCommandType;
export type CommandStatus = 'queued' | 'sent' | 'ack' | 'accepted' | 'applied' | 'completed' | 'rejected' | 'denied' | 'timeout' | 'cancelled' | 'superseded';
export type SourceType = 'frontend' | 'bridge' | 'ros2' | 'esp32' | 'stm32' | 'mock';
export type SafetyPhase = 'nominal' | 'degraded' | 'safe_stop' | 'fault_locked';
export type TaskPhase = 'idle' | 'running' | 'paused' | 'completed' | 'aborted' | 'interrupted';
export type DashboardPreset = 'demo' | 'ops' | 'debug';
export type DashboardBreakpoint = 'wide' | 'normal' | 'compact';
export type PanelId =
  | 'connection'
  | 'mode'
  | 'video'
  | 'power'
  | 'chassis'
  | 'vision'
  | 'voice'
  | 'fault'
  | 'commands'
  | 'logs'
  | 'history'
  | 'layout'
  | 'patrol'
  | 'inspector'
  | 'replay'
  | 'reports';

export interface DashboardPanelConfig {
  id: PanelId;
  order: number;
  colSpan: 1 | 2 | 3;
  rowSpan: 1 | 2;
}

export type DashboardLayouts = Record<DashboardPreset, DashboardPanelConfig[]>;

export interface ConnectionState {
  rosConnected: boolean;
  bridgeConnected: boolean;
  stm32Connected: boolean;
  videoConnected: boolean;
  voiceConnected: boolean;
  reconnecting: boolean;
  latencyMs: number;
  heartbeatAgeMs: number;
  lastHeartbeatAt: string | null;
  transportLabel: string;
  transportType: 'mock' | 'websocket';
  reconnectAttempts: number;
  staleMotion: boolean;
  stalePower: boolean;
  staleVision: boolean;
  staleVoice: boolean;
  inboundRateHz: number;
  outboundRateHz: number;
  protocolVersion: string;
  schemaVersion: string;
  capabilities: string[];
  lastSnapshotVersion: string | null;
  lastTraceId: string | null;
  compatibilityMode: 'native-v4';
  allowedTargetModes?: RobotMode[];
  modeReasons?: Partial<Record<RobotMode, string>>;
  commandPermissions?: Partial<Record<CommandType, { allowed: boolean; reason?: string }>>;
  safeStopRecoverable?: boolean;
  safeStopRequiresManualAck?: boolean;
  safeStopBlockedReason?: string | null;
  contractSource?: string;
  contractAuthority?: string;
  runtimeHealthState?: 'ready' | 'degraded' | 'unavailable';
  runtimeHealthReasons?: string[];
  wifiTransportReady?: boolean;
  uartBoardReady?: boolean;
  motionHeartbeatReady?: boolean;
  commandLinkReady?: boolean;
  gatewayReady?: boolean;
  gatewayReadyReasons?: string[];
  gatewayReadyTopic?: string | null;
  operatorSurfaceReady?: boolean;
  operatorSurfaceReadyReasons?: string[];
  operatorSurfaceReadyTopic?: string | null;
  operatorReady?: boolean;
  operatorReadyReasons?: string[];
  operatorReadyTopic?: string | null;
  sessionRole?: string;
  sessionRequestedRole?: string;
  sessionWriteEnabled?: boolean;
  sessionAccessReason?: string;
  sessionId?: string | null;
  sessionPolicySource?: string;
}


export interface MotionState {
  mode: RobotMode;
  linearVelocity: number;
  angularVelocity: number;
  leftWheelSpeed: number;
  rightWheelSpeed: number;
  odomX: number;
  odomY: number;
  odomYaw: number;
  isManualOverride: boolean;
  commandSource: 'ui' | 'voice' | 'task' | 'bridge' | 'unknown';
  lastUpdateAt: string | null;
}

export interface PowerState {
  batteryPercent: number;
  batteryVoltage: number;
  lowPowerWarning: boolean;
  charging: boolean;
  lastUpdateAt: string | null;
}

export interface VisionEvent {
  id: string;
  ts: string;
  label: string;
}

export interface VisionState {
  streamUrl: string;
  targetType: string | null;
  targetOffsetX: number;
  targetOffsetY: number;
  qrcodeText: string | null;
  detectTimestamp: string | null;
  frameDrops: number;
  trackingReady: boolean;
  lastUpdateAt: string | null;
  qrcodeHistory: VisionEvent[];
}

export interface VoiceEvent {
  id: string;
  ts: string;
  command: string;
  confidence: number;
}

export interface VoiceState {
  lastVoiceCommand: string | null;
  voiceConfidence: number;
  speaking: boolean;
  lastSpeakText: string | null;
  wakeStatus: 'idle' | 'listening' | 'triggered';
  lastUpdateAt: string | null;
  recentCommands: VoiceEvent[];
}

export interface WaypointStatus {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  note?: string;
}

export interface TaskState {
  patrolStatus: 'idle' | 'running' | 'paused' | 'completed' | 'aborted';
  currentWaypoint: string | null;
  progress: number;
  totalPoints: number;
  completedPoints: number;
  trackEnabled: boolean;
  lastTaskEvent: string | null;
  actionName?: string | null;
  actionPhase?: 'idle' | 'queued' | 'accepted' | 'running' | 'completed' | 'aborted' | 'cancelled';
  commandId?: string | null;
  commandType?: CommandType | null;
  lostTargetCount?: number;
  currentTargetType?: string | null;
  actionMessage?: string | null;
  actionProgress?: number;
  waypoints: WaypointStatus[];
}

export interface FaultState {
  level: FaultLevel;
  code: string | null;
  message: string | null;
  safeStopActive: boolean;
  estopActive: boolean;
  timeoutStopActive: boolean;
  lastUpdateAt: string | null;
}


export type ReportSurfaceEntry = GeneratedReportSurfaceEntry;
export type ReportsState = GeneratedReportsStatePayload;

export interface RuntimeState {
  safetyPhase: SafetyPhase;
  taskPhase: TaskPhase;
  lastRejectedReason: string | null;
  modeAudit: string;
}

export interface LogItem {
  id: string;
  timestamp: string;
  level: LogLevel;
  domain: LogDomain;
  message: string;
  details?: string;
}

export type ParamProfile = GeneratedParamProfile;
export type RuntimeParamApplyResult = GeneratedRuntimeParamApplyResult;
export type RuntimeParamConsumerStatus = GeneratedRuntimeParamConsumerStatus;
export type RuntimeParamTransactionState = GeneratedRuntimeParamTransactionState;
export type RuntimeParamProjectionState = 'committed' | 'provisional';
export type ParamProfileScope = 'runtime' | 'local';

export interface StoredProfiles {
  activeProfileName: string;
  profiles: Record<string, ParamProfile>;
  profileScopes: Record<string, ParamProfileScope>;
  draft: ParamProfile;
  applied: ParamProfile;
  configDigest: string | null;
  runtimeParamVersion: number;
  projectionState: RuntimeParamProjectionState;
  committedConfigDigest: string | null;
  committedProfileName: string;
  committedRuntimeParamVersion: number;
  lastParamApplyResult: RuntimeParamApplyResult | null;
  lastTransaction: RuntimeParamTransactionState | null;
}

export interface CommandRecord {
  id: string;
  type: CommandType;
  status: CommandStatus;
  createdAt: string;
  updatedAt: string;
  summary: string;
  priority: 'normal' | 'high' | 'critical';
  dangerous: boolean;
  requireAck: boolean;
  ackLatencyMs?: number;
  error?: string;
  retryCount?: number;
  source?: SourceType;
  dedupeKey?: string;
}

export interface HistoryState {
  latency: number[];
  battery: number[];
  leftWheel: number[];
  rightWheel: number[];
  frameDrops: number[];
  ackLatency: number[];
}

export interface InspectorRecord {
  id: string;
  timestamp: string;
  direction: 'in' | 'out' | 'rejected';
  type: string;
  verdict: 'accepted' | 'rejected' | 'sent';
  note?: string;
  raw: string;
}

export interface InspectorState {
  trace: InspectorRecord[];
}

export interface UiState {
  logKeyword: string;
  logLevel: 'ALL' | LogLevel;
  logDomain: 'ALL' | LogDomain;
  demoReadonly: boolean;
  dashboardPreset: DashboardPreset;
  panelVisibility: Record<PanelId, boolean>;
  dashboardLayouts: DashboardLayouts;
  activeBreakpoint: DashboardBreakpoint;
  lockedLayout: boolean;
}

export interface ReplaySession {
  kind?: 'offline-session-export';
  exportScope?: 'frontend-state-snapshot';
  exportedAt: string;
  sourceName: string;
  version?: string;
  logs: LogItem[];
  history: HistoryState;
  params: StoredProfiles;
  commands?: CommandRecord[];
  inspectorTrace?: InspectorRecord[];
}

export interface ReplayState {
  session: ReplaySession | null;
  activeLogIndex: number;
}

export type RobotSnapshot = GeneratedRobotSnapshot;

export interface EventEnvelope<TType extends string = string, TPayload = unknown> {
  eventId: string;
  type: TType;
  ts: string;
  source: SourceType;
  sessionId: string;
  seq: number;
  payload: TPayload;
  protocolVersion: string;
  schemaVersion: string;
  priority?: 'normal' | 'high' | 'critical';
  requireAck?: boolean;
  ttlMs?: number;
  dangerous?: boolean;
  operator?: string;
  reason?: string;
  traceId?: string;
  compatibilityMode?: 'native-v4';
  capabilities?: readonly string[];
  origin?: string;
  dedupeKey?: string;
  retryPolicy?: 'never' | 'once' | 'aggressive';
}

export type InboundEventType = GeneratedInboundEventType;

export type BridgeInboundPayloadMap = Record<InboundEventType, unknown> & GeneratedBridgeInboundPayloadMap;

type InboundPayloadFor<TType extends InboundEventType> = TType extends keyof GeneratedBridgeInboundPayloadMap ? GeneratedBridgeInboundPayloadMap[TType] : never;

export type BridgeInboundEvent = {
  [K in InboundEventType]: EventEnvelope<K, InboundPayloadFor<K>>;
}[InboundEventType];

export type BridgeLegacyInboundEvent = {
  type: InboundEventType;
  payload: BridgeInboundPayloadMap[InboundEventType];
};

export type BridgeOutboundPayloadMap = Record<CommandType, unknown> & GeneratedBridgeOutboundPayloadMap;

type OutboundPayloadFor<TType extends CommandType> = TType extends keyof GeneratedBridgeOutboundPayloadMap ? GeneratedBridgeOutboundPayloadMap[TType] : never;

export type BridgeOutboundEvent = {
  [K in CommandType]: EventEnvelope<K, OutboundPayloadFor<K>>;
}[CommandType];
