import type { GeneratedCommandType } from '@/generated/bridgeContract';

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
  compatibilityMode: 'native-v4' | 'legacy-v3' | 'legacy-v2';
  allowedTargetModes?: RobotMode[];
  modeReasons?: Partial<Record<RobotMode, string>>;
  commandPermissions?: Partial<Record<CommandType, { allowed: boolean; reason?: string }>>;
  safeStopRecoverable?: boolean;
  safeStopRequiresManualAck?: boolean;
  safeStopBlockedReason?: string | null;
  runtimeHealthState?: 'ready' | 'degraded' | 'unavailable';
  runtimeHealthReasons?: string[];
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

export interface ParamProfile {
  maxLinearSpeed: number;
  maxAngularSpeed: number;
  teleopStep: number;
  trackOffsetDeadband: number;
  lowPowerThreshold: number;
  reconnectTimeoutMs: number;
}

export interface RuntimeParamApplyResult {
  ok?: boolean;
  message?: string;
  ts?: string;
  reason?: string;
  traceId?: string;
  transactionId?: string;
  state?: 'pending' | 'applied' | 'failed' | 'timeout';
  rollbackPerformed?: boolean;
}

export interface RuntimeParamConsumerStatus {
  consumer: string;
  ok?: boolean | null;
  message?: string;
  state?: 'pending' | 'applied' | 'failed' | 'timeout';
  ts?: string;
  traceId?: string;
}

export interface RuntimeParamTransactionState {
  transactionId: string;
  ackMode: string;
  expectedConsumers: string[];
  consumerStatuses: Record<string, RuntimeParamConsumerStatus>;
  deadlineTs?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  state?: 'pending' | 'applied' | 'failed' | 'timeout';
  rollbackPerformed?: boolean;
}

export interface StoredProfiles {
  activeProfileName: string;
  profiles: Record<string, ParamProfile>;
  draft: ParamProfile;
  applied: ParamProfile;
  configDigest: string | null;
  runtimeParamVersion: number;
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

export interface RobotSnapshot {
  connection?: Partial<ConnectionState>;
  motion?: Partial<MotionState>;
  power?: Partial<PowerState>;
  vision?: Partial<VisionState>;
  voice?: Partial<VoiceState>;
  task?: Partial<TaskState>;
  fault?: Partial<FaultState>;
  params?: Partial<ParamProfile>;
  paramMetadata?: {
    configDigest?: string;
    activeProfileName?: string;
    runtimeParamVersion?: number;
    lastParamApplyResult?: RuntimeParamApplyResult | null;
    lastTransaction?: RuntimeParamTransactionState | null;
  };
  logs?: LogItem[];
}

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
  capabilities?: string[];
  origin?: string;
  dedupeKey?: string;
  retryPolicy?: 'never' | 'once' | 'aggressive';
}

export type InboundEventType =
  | 'heartbeat'
  | 'snapshot'
  | 'mode_state'
  | 'chassis_state'
  | 'power_state'
  | 'vision_target'
  | 'vision_qrcode'
  | 'voice_cmd'
  | 'task_event'
  | 'fault_event'
  | 'system_log'
  | 'command_ack';

export type BridgeInboundPayloadMap = {
  heartbeat: Partial<ConnectionState>;
  snapshot: RobotSnapshot;
  mode_state: Partial<MotionState>;
  chassis_state: Partial<MotionState>;
  power_state: Partial<PowerState>;
  vision_target: Partial<VisionState>;
  vision_qrcode: Pick<VisionState, 'qrcodeText' | 'detectTimestamp'>;
  voice_cmd: Partial<VoiceState>;
  task_event: Partial<TaskState>;
  fault_event: Partial<FaultState>;
  system_log: LogItem;
  command_ack: { commandId: string; status: Extract<CommandStatus, 'queued' | 'ack' | 'rejected' | 'denied' | 'timeout' | 'cancelled'>; lifecycleStatus?: Extract<CommandStatus, 'queued' | 'accepted' | 'applied' | 'completed' | 'rejected' | 'denied' | 'timeout' | 'cancelled'>; message?: string; detail?: string };
};

export type BridgeInboundEvent = {
  [K in InboundEventType]: EventEnvelope<K, BridgeInboundPayloadMap[K]>;
}[InboundEventType];

export type BridgeLegacyInboundEvent = {
  type: InboundEventType;
  payload: BridgeInboundPayloadMap[InboundEventType];
};

export type BridgeOutboundPayloadMap = {
  set_mode: { mode: RobotMode; source: 'frontend' };
  teleop_cmd: { linear: number; angular: number; source: 'frontend' };
  stop_now: { source: 'frontend' };
  estop: { source: 'frontend' };
  resume_from_safe_stop: { source: 'frontend' };
  start_patrol: { source: 'frontend' };
  pause_patrol: { source: 'frontend' };
  stop_patrol: { source: 'frontend' };
  set_param: { key: keyof ParamProfile; value: number; source: 'frontend' };
  apply_param_profile: { profileName: string; source: 'frontend' };
  speak_fixed_text: { text: string; source: 'frontend' };
  reset_fault: { source: 'frontend' };
  save_snapshot: { source: 'frontend' };
};

export type BridgeOutboundEvent = {
  [K in CommandType]: EventEnvelope<K, BridgeOutboundPayloadMap[K]>;
}[CommandType];
