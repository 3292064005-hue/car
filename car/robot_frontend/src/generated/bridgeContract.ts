import { z } from 'zod';

export const WEB_PROTOCOL_VERSION = '4.1.0' as const;
export const WEB_SCHEMA_VERSION = '2026-03-31' as const;
export const TRANSPORT_PROTOCOL_VERSION = '1' as const;
export const UART_PROTOCOL_VERSION = '1' as const;
export const PROTOCOL_VERSION = WEB_PROTOCOL_VERSION;
export const SCHEMA_VERSION = WEB_SCHEMA_VERSION;
export const COMPATIBILITY_MODES = ["native-v4", "legacy-v3", "legacy-v2"] as const;
export const BRIDGE_CAPABILITIES = ["command-ack", "session-replay", "layout-presets", "reports-export", "protocol-versioning", "odom-bridge", "battery-state", "transport-diagnostics", "fault-dictionary", "stale-flags", "compatibility-mode", "trace-correlation", "runtime-param-sync", "mode-capability-snapshot", "action-workflows", "qos-matrix", "web-bridge-components", "frontend-slices", "runtime-health-snapshot", "command-lifecycle-v2"] as const;
export const COMMAND_TYPES = ["set_mode", "teleop_cmd", "stop_now", "estop", "resume_from_safe_stop", "start_patrol", "pause_patrol", "stop_patrol", "set_param", "apply_param_draft", "apply_param_profile", "speak_fixed_text", "reset_fault", "save_snapshot"] as const;
export const INBOUND_EVENT_TYPES = ["snapshot", "heartbeat", "connection_state", "mode_state", "chassis_state", "power_state", "vision_target", "vision_qrcode", "voice_cmd", "fault_event", "system_log", "task_event", "command_ack"] as const;
export type GeneratedCommandType = typeof COMMAND_TYPES[number];
export type GeneratedInboundEventType = typeof INBOUND_EVENT_TYPES[number];

export const sourceSchema = z.enum(['frontend', 'bridge', 'ros2', 'esp32', 'stm32', 'mock']);
export const robotModeSchema = z.enum(['BOOT', 'IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT']);
export const logLevelSchema = z.enum(['INFO', 'WARN', 'ERROR', 'CRITICAL']);
export const logDomainSchema = z.enum(['SYSTEM', 'BRIDGE', 'CONTROL', 'VISION', 'VOICE', 'TASK', 'SAFETY', 'PARAM', 'REPLAY', 'INSPECTOR', 'REPORT']);
export const commandAckStatusSchema = z.enum(['queued', 'ack', 'rejected', 'denied', 'timeout', 'cancelled']);
export const commandLifecycleStatusSchema = z.enum(['queued', 'accepted', 'applied', 'completed', 'rejected', 'denied', 'timeout', 'cancelled']);
export const commandPhaseSchema = z.enum(['idle', 'queued', 'accepted', 'running', 'completed', 'aborted', 'cancelled']);
export const wakeStatusSchema = z.enum(['idle', 'listening', 'triggered']);
export const compatibilityModeSchema = z.enum(COMPATIBILITY_MODES);
export const runtimeHealthStateSchema = z.enum(['ready', 'degraded', 'unavailable']);
export const faultLevelSchema = z.enum(['info', 'warning', 'critical']);
export const commandSourceSchema = z.enum(['ui', 'voice', 'task', 'bridge', 'unknown']);
export const transportTypeSchema = z.enum(['mock', 'websocket']);
export const patrolStatusSchema = z.enum(['idle', 'running', 'paused', 'completed', 'aborted']);
export const waypointStatusSchema = z.enum(['pending', 'running', 'done', 'failed']);
export const runtimeTransactionStatusSchema = z.enum(['pending', 'applied', 'failed', 'timeout']);
export const runtimeProjectionStateSchema = z.enum(['committed', 'provisional']);

export const commandPermissionSchema = z.object({
  allowed: z.boolean(),
  reason: z.string().optional(),
});

export const paramProfileSchema = z.object({
  maxLinearSpeed: z.number(),
  maxAngularSpeed: z.number(),
  teleopStep: z.number(),
  trackOffsetDeadband: z.number(),
  lowPowerThreshold: z.number(),
  reconnectTimeoutMs: z.number(),
});
export type GeneratedParamProfile = z.infer<typeof paramProfileSchema>;
export type GeneratedParamProfileKey = keyof GeneratedParamProfile;

export const runtimeParamApplyResultSchema = z.object({
  ok: z.boolean().optional(),
  message: z.string().optional(),
  ts: z.string().optional(),
  reason: z.string().optional(),
  traceId: z.string().optional(),
  transactionId: z.string().optional(),
  state: runtimeTransactionStatusSchema.optional(),
  rollbackPerformed: z.boolean().optional(),
});
export type GeneratedRuntimeParamApplyResult = z.infer<typeof runtimeParamApplyResultSchema>;

export const runtimeParamConsumerStatusSchema = z.object({
  consumer: z.string(),
  ok: z.boolean().nullable().optional(),
  message: z.string().optional(),
  state: runtimeTransactionStatusSchema.optional(),
  ts: z.string().optional(),
  traceId: z.string().optional(),
});
export type GeneratedRuntimeParamConsumerStatus = z.infer<typeof runtimeParamConsumerStatusSchema>;

export const runtimeParamTransactionStateSchema = z.object({
  transactionId: z.string().default(''),
  ackMode: z.string().default(''),
  expectedConsumers: z.array(z.string()).default([]),
  consumerStatuses: z.record(z.string(), runtimeParamConsumerStatusSchema).default({}),
  deadlineTs: z.string().nullable().optional(),
  startedAt: z.string().nullable().optional(),
  completedAt: z.string().nullable().optional(),
  state: runtimeTransactionStatusSchema.optional(),
  rollbackPerformed: z.boolean().optional(),
});
export type GeneratedRuntimeParamTransactionState = z.infer<typeof runtimeParamTransactionStateSchema>;

export const visionEventSchema = z.object({ id: z.string(), ts: z.string(), label: z.string() });
export const voiceEventSchema = z.object({ id: z.string(), ts: z.string(), command: z.string(), confidence: z.number() });
export const waypointStatusItemSchema = z.object({ id: z.string(), label: z.string(), status: waypointStatusSchema, note: z.string().optional() });
export const logItemSchema = z.object({
  id: z.string().min(1),
  timestamp: z.string().min(1),
  level: logLevelSchema,
  domain: logDomainSchema,
  message: z.string().min(1),
  details: z.string().optional(),
});
export type GeneratedLogItem = z.infer<typeof logItemSchema>;

export const connectionStatePayloadSchema = z.object({
  rosConnected: z.boolean().optional(),
  bridgeConnected: z.boolean().optional(),
  stm32Connected: z.boolean().optional(),
  videoConnected: z.boolean().optional(),
  voiceConnected: z.boolean().optional(),
  reconnecting: z.boolean().optional(),
  latencyMs: z.number().optional(),
  heartbeatAgeMs: z.number().optional(),
  lastHeartbeatAt: z.string().nullable().optional(),
  transportLabel: z.string().optional(),
  transportType: transportTypeSchema.optional(),
  reconnectAttempts: z.number().optional(),
  staleMotion: z.boolean().optional(),
  stalePower: z.boolean().optional(),
  staleVision: z.boolean().optional(),
  staleVoice: z.boolean().optional(),
  inboundRateHz: z.number().optional(),
  outboundRateHz: z.number().optional(),
  protocolVersion: z.string().optional(),
  schemaVersion: z.string().optional(),
  capabilities: z.array(z.string()).optional(),
  lastSnapshotVersion: z.string().nullable().optional(),
  lastTraceId: z.string().nullable().optional(),
  compatibilityMode: compatibilityModeSchema.optional(),
  allowedTargetModes: z.array(robotModeSchema).optional(),
  modeReasons: z.record(z.string(), z.string()).optional(),
  commandPermissions: z.record(z.string(), commandPermissionSchema).optional(),
  safeStopRecoverable: z.boolean().optional(),
  safeStopRequiresManualAck: z.boolean().optional(),
  safeStopBlockedReason: z.string().nullable().optional(),
  runtimeHealthState: runtimeHealthStateSchema.optional(),
  runtimeHealthReasons: z.array(z.string()).optional(),
  operatorReady: z.boolean().optional(),
  operatorReadyReasons: z.array(z.string()).optional(),
  operatorReadyTopic: z.string().nullable().optional(),
  sessionRole: z.string().optional(),
  sessionRequestedRole: z.string().optional(),
  sessionWriteEnabled: z.boolean().optional(),
  sessionAccessReason: z.string().optional(),
  sessionId: z.string().optional(),
  sessionPolicySource: z.string().optional(),
});
export type GeneratedConnectionStatePayload = z.infer<typeof connectionStatePayloadSchema>;

export const motionStatePayloadSchema = z.object({
  mode: robotModeSchema.optional(),
  linearVelocity: z.number().optional(),
  angularVelocity: z.number().optional(),
  leftWheelSpeed: z.number().optional(),
  rightWheelSpeed: z.number().optional(),
  odomX: z.number().optional(),
  odomY: z.number().optional(),
  odomYaw: z.number().optional(),
  isManualOverride: z.boolean().optional(),
  commandSource: commandSourceSchema.optional(),
  lastUpdateAt: z.string().nullable().optional(),
});
export type GeneratedMotionStatePayload = z.infer<typeof motionStatePayloadSchema>;

export const powerStatePayloadSchema = z.object({
  batteryPercent: z.number().optional(),
  batteryVoltage: z.number().optional(),
  lowPowerWarning: z.boolean().optional(),
  charging: z.boolean().optional(),
  lastUpdateAt: z.string().nullable().optional(),
});
export type GeneratedPowerStatePayload = z.infer<typeof powerStatePayloadSchema>;

export const visionStatePayloadSchema = z.object({
  streamUrl: z.string().optional(),
  targetType: z.string().nullable().optional(),
  targetOffsetX: z.number().optional(),
  targetOffsetY: z.number().optional(),
  qrcodeText: z.string().nullable().optional(),
  detectTimestamp: z.string().nullable().optional(),
  frameDrops: z.number().optional(),
  trackingReady: z.boolean().optional(),
  lastUpdateAt: z.string().nullable().optional(),
  qrcodeHistory: z.array(visionEventSchema).optional(),
});
export type GeneratedVisionStatePayload = z.infer<typeof visionStatePayloadSchema>;

export const visionQrPayloadSchema = z.object({
  qrcodeText: z.string().nullable().optional(),
  detectTimestamp: z.string().nullable().optional(),
});
export type GeneratedVisionQrPayload = z.infer<typeof visionQrPayloadSchema>;

export const voiceStatePayloadSchema = z.object({
  lastVoiceCommand: z.string().nullable().optional(),
  voiceConfidence: z.number().optional(),
  speaking: z.boolean().optional(),
  lastSpeakText: z.string().nullable().optional(),
  wakeStatus: wakeStatusSchema.optional(),
  lastUpdateAt: z.string().nullable().optional(),
  recentCommands: z.array(voiceEventSchema).optional(),
});
export type GeneratedVoiceStatePayload = z.infer<typeof voiceStatePayloadSchema>;

export const taskStatePayloadSchema = z.object({
  patrolStatus: patrolStatusSchema.optional(),
  currentWaypoint: z.string().nullable().optional(),
  progress: z.number().optional(),
  totalPoints: z.number().optional(),
  completedPoints: z.number().optional(),
  trackEnabled: z.boolean().optional(),
  lastTaskEvent: z.string().nullable().optional(),
  actionName: z.string().nullable().optional(),
  actionPhase: commandPhaseSchema.optional(),
  commandId: z.string().nullable().optional(),
  commandType: z.enum(COMMAND_TYPES).optional(),
  lostTargetCount: z.number().optional(),
  currentTargetType: z.string().nullable().optional(),
  actionMessage: z.string().nullable().optional(),
  actionProgress: z.number().optional(),
  waypoints: z.array(waypointStatusItemSchema).optional(),
});
export type GeneratedTaskStatePayload = z.infer<typeof taskStatePayloadSchema>;

export const faultStatePayloadSchema = z.object({
  level: faultLevelSchema.optional(),
  code: z.string().nullable().optional(),
  message: z.string().nullable().optional(),
  safeStopActive: z.boolean().optional(),
  estopActive: z.boolean().optional(),
  timeoutStopActive: z.boolean().optional(),
  lastUpdateAt: z.string().nullable().optional(),
});
export type GeneratedFaultStatePayload = z.infer<typeof faultStatePayloadSchema>;

export const runtimeParamMetadataSchema = z.object({
  configDigest: z.string().optional(),
  activeProfileName: z.string().optional(),
  runtimeParamVersion: z.number().optional(),
  lastParamApplyResult: runtimeParamApplyResultSchema.nullable().optional(),
  lastTransaction: runtimeParamTransactionStateSchema.nullable().optional(),
  projectionState: runtimeProjectionStateSchema.optional(),
  committedConfigDigest: z.string().optional(),
  committedProfileName: z.string().optional(),
  committedRuntimeParamVersion: z.number().optional(),
});
export type GeneratedRuntimeParamMetadata = z.infer<typeof runtimeParamMetadataSchema>;


export const reportSeveritySchema = z.enum(['info', 'success', 'warn', 'error']);
export const reportKindSchema = z.enum(['control_summary', 'monitor_summary', 'monitor_diagnostics', 'localization_summary', 'hardware_interface_summary', 'navigation_status', 'navigation_path', 'runtime_supervision']);

export const reportSelectedCommandSchema = z.object({
  vx: z.number().nullable().optional(),
  wz: z.number().nullable().optional(),
});
export const reportCandidateSchema = z.object({
  source: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
  fresh: z.boolean().nullable().optional(),
  eligible: z.boolean().nullable().optional(),
  selected: z.boolean().optional(),
});
export const reportControlSummaryDetailsSchema = z.object({
  winner: z.string(),
  safetyReason: z.string(),
  powerReason: z.string(),
  selectedAgeSec: z.number().nullable().optional(),
  selectedCommand: reportSelectedCommandSchema.optional(),
  arbitration: z.object({
    selectedSource: z.string().nullable().optional(),
    selectionReason: z.string().nullable().optional(),
    candidates: z.array(reportCandidateSchema).optional(),
  }).passthrough().optional(),
  rejectedCandidates: z.array(reportCandidateSchema).optional(),
});
export const reportMonitorSummaryDetailsSchema = z.object({
  health: z.string(),
  readiness: z.string(),
  reason: z.string(),
  mode: z.string(),
  wifiOk: z.boolean(),
  bridgeOk: z.boolean(),
  cameraOk: z.boolean(),
  audioOk: z.boolean(),
  uartOk: z.boolean(),
  batteryVoltage: z.number(),
  leftRpm: z.number(),
  rightRpm: z.number(),
  controlSource: z.string(),
  lastQrcode: z.string(),
  lastVoiceCommand: z.string(),
  lastFault: z.string(),
  snapshotCount: z.number(),
  reconnectCount: z.number(),
  protocolErrors: z.number(),
  recentSummary: z.string(),
});
export const reportRuntimeSupervisionLifecycleNodeSchema = z.object({
  wrapperName: z.string().optional(),
  componentId: z.string().optional(),
  actualState: z.string().optional(),
  desiredState: z.string().optional(),
  bondState: z.string().optional(),
  optional: z.boolean().optional(),
  lastError: z.string().nullable().optional(),
}).passthrough();
export const reportRuntimeSupervisionBondNodeSchema = z.object({
  wrapperName: z.string().optional(),
  componentId: z.string().optional(),
  bondState: z.string().optional(),
}).passthrough();
export const reportRuntimeSupervisionLifecycleSchema = z.object({
  present: z.boolean().optional(),
  type: z.string().optional(),
  state: z.string().optional(),
  managedNodes: z.array(reportRuntimeSupervisionLifecycleNodeSchema).optional(),
  recentTransitions: z.array(z.object({
    subject: z.string().optional(),
    fromState: z.string().optional(),
    toState: z.string().optional(),
    reason: z.string().optional(),
    ts: z.union([z.string(), z.number()]).optional(),
  }).passthrough()).optional(),
}).passthrough();
export const reportRuntimeSupervisionBondSchema = z.object({
  present: z.boolean().optional(),
  type: z.string().optional(),
  state: z.string().optional(),
  managedNodes: z.array(reportRuntimeSupervisionBondNodeSchema).optional(),
}).passthrough();
export const reportRuntimeSupervisionRecoveryPlanSchema = z.object({
  strategy: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
  targetNodes: z.array(z.string()).optional(),
}).passthrough();
export const reportMonitorDiagnosticsDetailsSchema = z.object({
  componentStatusCount: z.number(),
  unhealthyCount: z.number(),
  unhealthyComponents: z.array(z.string()),
  systemStatus: z.object({
    name: z.string(),
    level: z.string(),
    message: z.string(),
  }),
  runtimeState: z.string(),
  runtimeReasons: z.array(z.string()),
});
export const reportLocalizationPoseSchema = z.object({
  x: z.number().optional(),
  y: z.number().optional(),
  yaw: z.number().optional(),
}).passthrough();
export const reportLocalizationSummaryDetailsSchema = z.object({
  feedbackAvailable: z.boolean(),
  stale: z.boolean(),
  pose: reportLocalizationPoseSchema.optional(),
  robotName: z.string().nullable().optional(),
  descriptionLoaded: z.boolean().nullable().optional(),
});
export const reportHardwareInterfaceSummaryDetailsSchema = z.object({
  jointStateAvailable: z.boolean(),
  batteryStateAvailable: z.boolean(),
  cmdObserved: z.boolean(),
  batteryPercent: z.number().nullable().optional(),
  batteryVoltage: z.number().nullable().optional(),
  missing: z.array(z.string()),
});
export const reportNavigationStatusDetailsSchema = z.object({
  routeName: z.string().nullable().optional(),
  goal: z.string().nullable().optional(),
  completedGoals: z.number(),
  totalGoals: z.number(),
  progress: z.number(),
  reason: z.string().nullable().optional(),
});
export const reportNavigationPathDetailsSchema = z.object({
  poseCount: z.number().nullable().optional(),
  hasPath: z.boolean().nullable().optional(),
}).passthrough();
export const reportRuntimeSupervisionDetailsSchema = z.object({
  reasons: z.array(z.string()),
  startupBarrierReady: z.boolean(),
  readiness: z.string().nullable().optional(),
  recoveryMode: z.string().nullable().optional(),
  lifecycleManager: reportRuntimeSupervisionLifecycleSchema,
  bondSupervision: reportRuntimeSupervisionBondSchema,
  recoveryPlan: reportRuntimeSupervisionRecoveryPlanSchema,
});

export const reportSurfaceEntryBaseSchema = z.object({
  topic: z.string().optional(),
  raw: z.string().optional(),
  parsed: z.unknown().optional(),
  updatedAt: z.string().nullable().optional(),
  severity: reportSeveritySchema.optional(),
  summary: z.string().optional(),
  status: z.string().optional(),
});
export const reportControlSummaryEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('control_summary'),
  details: reportControlSummaryDetailsSchema,
});
export const reportMonitorSummaryEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('monitor_summary'),
  details: reportMonitorSummaryDetailsSchema,
});
export const reportMonitorDiagnosticsEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('monitor_diagnostics'),
  details: reportMonitorDiagnosticsDetailsSchema,
});
export const reportLocalizationSummaryEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('localization_summary'),
  details: reportLocalizationSummaryDetailsSchema,
});
export const reportHardwareInterfaceSummaryEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('hardware_interface_summary'),
  details: reportHardwareInterfaceSummaryDetailsSchema,
});
export const reportNavigationStatusEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('navigation_status'),
  details: reportNavigationStatusDetailsSchema,
});
export const reportNavigationPathEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('navigation_path'),
  details: reportNavigationPathDetailsSchema,
});
export const reportRuntimeSupervisionEntrySchema = reportSurfaceEntryBaseSchema.extend({
  kind: z.literal('runtime_supervision'),
  details: reportRuntimeSupervisionDetailsSchema,
});
export const reportSurfaceEntrySchema = z.discriminatedUnion('kind', [
  reportControlSummaryEntrySchema,
  reportMonitorSummaryEntrySchema,
  reportMonitorDiagnosticsEntrySchema,
  reportLocalizationSummaryEntrySchema,
  reportHardwareInterfaceSummaryEntrySchema,
  reportNavigationStatusEntrySchema,
  reportNavigationPathEntrySchema,
  reportRuntimeSupervisionEntrySchema,
]);
export type GeneratedReportSurfaceEntry = z.infer<typeof reportSurfaceEntrySchema>;

export const reportsStatePayloadSchema = z.object({
  controlSummary: reportSurfaceEntrySchema.optional(),
  monitorSummary: reportSurfaceEntrySchema.optional(),
  monitorDiagnostics: reportSurfaceEntrySchema.optional(),
  localizationSummary: reportSurfaceEntrySchema.optional(),
  hardwareInterfaceSummary: reportSurfaceEntrySchema.optional(),
  navigationStatus: reportSurfaceEntrySchema.optional(),
  navigationPath: reportSurfaceEntrySchema.optional(),
  runtimeSupervision: reportSurfaceEntrySchema.optional(),
});
export type GeneratedReportsStatePayload = z.infer<typeof reportsStatePayloadSchema>;

export const robotSnapshotSchema = z.object({
  connection: connectionStatePayloadSchema.optional(),
  motion: motionStatePayloadSchema.optional(),
  power: powerStatePayloadSchema.optional(),
  vision: visionStatePayloadSchema.optional(),
  voice: voiceStatePayloadSchema.optional(),
  task: taskStatePayloadSchema.optional(),
  fault: faultStatePayloadSchema.optional(),
  reports: reportsStatePayloadSchema.optional(),
  params: paramProfileSchema.partial().optional(),
  paramMetadata: runtimeParamMetadataSchema.optional(),
  logs: z.array(logItemSchema).optional(),
});
export type GeneratedRobotSnapshot = z.infer<typeof robotSnapshotSchema>;

export const commandAckPayloadSchema = z.object({
  commandId: z.string().min(1),
  status: commandAckStatusSchema,
  lifecycleStatus: commandLifecycleStatusSchema.optional(),
  message: z.string().optional(),
  detail: z.string().optional(),
});
export type GeneratedCommandAckPayload = z.infer<typeof commandAckPayloadSchema>;

export const inboundPayloadSchemas = {
  heartbeat: connectionStatePayloadSchema,
  snapshot: robotSnapshotSchema,
  connection_state: connectionStatePayloadSchema,
  mode_state: motionStatePayloadSchema,
  chassis_state: motionStatePayloadSchema,
  power_state: powerStatePayloadSchema,
  vision_target: visionStatePayloadSchema,
  vision_qrcode: visionQrPayloadSchema,
  voice_cmd: voiceStatePayloadSchema,
  fault_event: faultStatePayloadSchema,
  system_log: logItemSchema,
  task_event: taskStatePayloadSchema,
  command_ack: commandAckPayloadSchema,
} as const satisfies Record<GeneratedInboundEventType, z.ZodTypeAny>;

export type GeneratedBridgeInboundPayloadMap = {
  heartbeat: GeneratedConnectionStatePayload;
  snapshot: GeneratedRobotSnapshot;
  connection_state: GeneratedConnectionStatePayload;
  mode_state: GeneratedMotionStatePayload;
  chassis_state: GeneratedMotionStatePayload;
  power_state: GeneratedPowerStatePayload;
  vision_target: GeneratedVisionStatePayload;
  vision_qrcode: GeneratedVisionQrPayload;
  voice_cmd: GeneratedVoiceStatePayload;
  fault_event: GeneratedFaultStatePayload;
  system_log: GeneratedLogItem;
  task_event: GeneratedTaskStatePayload;
  command_ack: GeneratedCommandAckPayload;
};

export const inboundTypeSchema = z.enum(INBOUND_EVENT_TYPES);

export const outboundPayloadSchemas = {
  set_mode: z.object({ mode: robotModeSchema, source: z.literal('frontend') }),
  teleop_cmd: z.object({ linear: z.number(), angular: z.number(), source: z.literal('frontend') }),
  stop_now: z.object({ source: z.literal('frontend') }),
  estop: z.object({ source: z.literal('frontend') }),
  resume_from_safe_stop: z.object({ source: z.literal('frontend') }),
  start_patrol: z.object({ source: z.literal('frontend') }),
  pause_patrol: z.object({ source: z.literal('frontend') }),
  stop_patrol: z.object({ source: z.literal('frontend') }),
  set_param: z.object({ key: z.enum(['maxLinearSpeed', 'maxAngularSpeed', 'teleopStep', 'trackOffsetDeadband', 'lowPowerThreshold', 'reconnectTimeoutMs']), value: z.number(), source: z.literal('frontend') }),
  apply_param_draft: z.object({ params: paramProfileSchema, source: z.literal('frontend') }),
  apply_param_profile: z.object({ profileName: z.string(), source: z.literal('frontend') }),
  speak_fixed_text: z.object({ text: z.string(), source: z.literal('frontend') }),
  reset_fault: z.object({ source: z.literal('frontend') }),
  save_snapshot: z.object({ source: z.literal('frontend') }),
} as const satisfies Record<GeneratedCommandType, z.ZodTypeAny>;

export type GeneratedBridgeOutboundPayloadMap = {
  set_mode: z.infer<typeof outboundPayloadSchemas.set_mode>;
  teleop_cmd: z.infer<typeof outboundPayloadSchemas.teleop_cmd>;
  stop_now: z.infer<typeof outboundPayloadSchemas.stop_now>;
  estop: z.infer<typeof outboundPayloadSchemas.estop>;
  resume_from_safe_stop: z.infer<typeof outboundPayloadSchemas.resume_from_safe_stop>;
  start_patrol: z.infer<typeof outboundPayloadSchemas.start_patrol>;
  pause_patrol: z.infer<typeof outboundPayloadSchemas.pause_patrol>;
  stop_patrol: z.infer<typeof outboundPayloadSchemas.stop_patrol>;
  set_param: z.infer<typeof outboundPayloadSchemas.set_param>;
  apply_param_draft: z.infer<typeof outboundPayloadSchemas.apply_param_draft>;
  apply_param_profile: z.infer<typeof outboundPayloadSchemas.apply_param_profile>;
  speak_fixed_text: z.infer<typeof outboundPayloadSchemas.speak_fixed_text>;
  reset_fault: z.infer<typeof outboundPayloadSchemas.reset_fault>;
  save_snapshot: z.infer<typeof outboundPayloadSchemas.save_snapshot>;
};
