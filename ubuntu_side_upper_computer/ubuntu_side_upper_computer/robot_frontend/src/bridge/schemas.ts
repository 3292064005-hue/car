import { z } from 'zod';
import { PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';
import type { BridgeInboundEvent, BridgeOutboundEvent, InboundEventType } from '@/types/robot';

const sourceSchema = z.enum(['frontend', 'bridge', 'ros2', 'esp32', 'stm32', 'mock']);
const robotModeSchema = z.enum(['BOOT', 'IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT']);
const logLevelSchema = z.enum(['INFO', 'WARN', 'ERROR', 'CRITICAL']);
const logDomainSchema = z.enum(['SYSTEM', 'BRIDGE', 'CONTROL', 'VISION', 'VOICE', 'TASK', 'SAFETY', 'PARAM', 'REPLAY', 'INSPECTOR', 'REPORT']);
const commandStatusSchema = z.enum(['queued', 'ack', 'rejected', 'denied', 'timeout', 'cancelled']);
const commandLifecycleStatusSchema = z.enum(['queued', 'accepted', 'applied', 'completed', 'rejected', 'denied', 'timeout', 'cancelled']);

const envelopeBase = z.object({
  eventId: z.string().min(1),
  type: z.string().min(1),
  ts: z.string().min(1),
  source: sourceSchema,
  sessionId: z.string().min(1),
  seq: z.number().int().nonnegative(),
  payload: z.unknown(),
  protocolVersion: z.string().default(PROTOCOL_VERSION),
  schemaVersion: z.string().default(SCHEMA_VERSION),
  compatibilityMode: z.enum(['native-v4', 'legacy-v3', 'legacy-v2']).optional(),
  priority: z.enum(['normal', 'high', 'critical']).optional(),
  requireAck: z.boolean().optional(),
  ttlMs: z.number().optional(),
  dangerous: z.boolean().optional(),
  operator: z.string().optional(),
  reason: z.string().optional(),
  traceId: z.string().optional(),
  capabilities: z.array(z.string()).optional(),
  origin: z.string().optional(),
  dedupeKey: z.string().optional(),
  retryPolicy: z.enum(['never', 'once', 'aggressive']).optional()
});

const partialConnectionSchema = z.object({
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
  transportType: z.enum(['mock', 'websocket']).optional(),
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
  compatibilityMode: z.enum(['native-v4', 'legacy-v3', 'legacy-v2']).optional(),
  allowedTargetModes: z.array(robotModeSchema).optional(),
  modeReasons: z.record(z.string(), z.string()).optional(),
  commandPermissions: z.record(z.string(), z.object({ allowed: z.boolean(), reason: z.string().optional() })).optional(),
  safeStopRecoverable: z.boolean().optional(),
  safeStopRequiresManualAck: z.boolean().optional(),
  safeStopBlockedReason: z.string().nullable().optional(),
  runtimeHealthState: z.enum(['ready', 'degraded', 'unavailable']).optional(),
  runtimeHealthReasons: z.array(z.string()).optional()
});

const partialMotionSchema = z.object({
  mode: robotModeSchema.optional(),
  linearVelocity: z.number().optional(),
  angularVelocity: z.number().optional(),
  leftWheelSpeed: z.number().optional(),
  rightWheelSpeed: z.number().optional(),
  odomX: z.number().optional(),
  odomY: z.number().optional(),
  odomYaw: z.number().optional(),
  isManualOverride: z.boolean().optional(),
  commandSource: z.enum(['ui', 'voice', 'task', 'bridge', 'unknown']).optional(),
  lastUpdateAt: z.string().nullable().optional()
});

const partialPowerSchema = z.object({
  batteryPercent: z.number().optional(),
  batteryVoltage: z.number().optional(),
  lowPowerWarning: z.boolean().optional(),
  charging: z.boolean().optional(),
  lastUpdateAt: z.string().nullable().optional()
});

const partialVisionSchema = z.object({
  streamUrl: z.string().optional(),
  targetType: z.string().nullable().optional(),
  targetOffsetX: z.number().optional(),
  targetOffsetY: z.number().optional(),
  qrcodeText: z.string().nullable().optional(),
  detectTimestamp: z.string().nullable().optional(),
  frameDrops: z.number().optional(),
  trackingReady: z.boolean().optional(),
  lastUpdateAt: z.string().nullable().optional(),
  qrcodeHistory: z.array(z.object({ id: z.string(), ts: z.string(), label: z.string() })).optional()
});

const partialVoiceSchema = z.object({
  lastVoiceCommand: z.string().nullable().optional(),
  voiceConfidence: z.number().optional(),
  speaking: z.boolean().optional(),
  lastSpeakText: z.string().nullable().optional(),
  wakeStatus: z.enum(['idle', 'listening', 'triggered']).optional(),
  lastUpdateAt: z.string().nullable().optional(),
  recentCommands: z.array(z.object({ id: z.string(), ts: z.string(), command: z.string(), confidence: z.number() })).optional()
});

const partialTaskSchema = z.object({
  patrolStatus: z.enum(['idle', 'running', 'paused', 'completed', 'aborted']).optional(),
  currentWaypoint: z.string().nullable().optional(),
  progress: z.number().optional(),
  totalPoints: z.number().optional(),
  completedPoints: z.number().optional(),
  trackEnabled: z.boolean().optional(),
  lastTaskEvent: z.string().nullable().optional(),
  actionName: z.string().nullable().optional(),
  actionPhase: z.enum(['idle', 'queued', 'accepted', 'running', 'completed', 'aborted', 'cancelled']).optional(),
  commandId: z.string().nullable().optional(),
  commandType: z.string().nullable().optional(),
  lostTargetCount: z.number().optional(),
  currentTargetType: z.string().nullable().optional(),
  actionMessage: z.string().nullable().optional(),
  actionProgress: z.number().optional(),
  waypoints: z.array(z.object({ id: z.string(), label: z.string(), status: z.enum(['pending', 'running', 'done', 'failed']), note: z.string().optional() })).optional()
});

const partialFaultSchema = z.object({
  level: z.enum(['info', 'warning', 'critical']).optional(),
  code: z.string().nullable().optional(),
  message: z.string().nullable().optional(),
  safeStopActive: z.boolean().optional(),
  estopActive: z.boolean().optional(),
  timeoutStopActive: z.boolean().optional(),
  lastUpdateAt: z.string().nullable().optional()
});

const logSchema = z.object({
  id: z.string().min(1),
  timestamp: z.string().min(1),
  level: logLevelSchema,
  domain: logDomainSchema,
  message: z.string().min(1),
  details: z.string().optional()
});

const snapshotSchema = z.object({
  connection: partialConnectionSchema.optional(),
  motion: partialMotionSchema.optional(),
  power: partialPowerSchema.optional(),
  vision: partialVisionSchema.optional(),
  voice: partialVoiceSchema.optional(),
  task: partialTaskSchema.optional(),
  fault: partialFaultSchema.optional(),
  params: z
    .object({
      maxLinearSpeed: z.number().optional(),
      maxAngularSpeed: z.number().optional(),
      teleopStep: z.number().optional(),
      trackOffsetDeadband: z.number().optional(),
      lowPowerThreshold: z.number().optional(),
      reconnectTimeoutMs: z.number().optional()
    })
    .optional(),
  paramMetadata: z.object({
    configDigest: z.string().optional(),
    activeProfileName: z.string().optional(),
    runtimeParamVersion: z.number().optional(),
    lastParamApplyResult: z.object({
      ok: z.boolean().optional(),
      message: z.string().optional(),
      ts: z.string().optional(),
      reason: z.string().optional(),
      traceId: z.string().optional(),
      transactionId: z.string().optional(),
      state: z.enum(['pending', 'applied', 'failed', 'timeout']).optional(),
      rollbackPerformed: z.boolean().optional()
    }).nullable().optional(),
    lastTransaction: z.object({
      transactionId: z.string().default(''),
      ackMode: z.string().default(''),
      expectedConsumers: z.array(z.string()).default([]),
      consumerStatuses: z.record(z.string(), z.object({
        consumer: z.string(),
        ok: z.boolean().nullable().optional(),
        message: z.string().optional(),
        state: z.enum(['pending', 'applied', 'failed', 'timeout']).optional(),
        ts: z.string().optional(),
        traceId: z.string().optional()
      })).default({}),
      deadlineTs: z.string().nullable().optional(),
      startedAt: z.string().nullable().optional(),
      completedAt: z.string().nullable().optional(),
      state: z.enum(['pending', 'applied', 'failed', 'timeout']).optional()
    }).nullable().optional()
  }).optional(),
  logs: z.array(logSchema).optional()
});

const payloadSchemas: Record<InboundEventType, z.ZodTypeAny> = {
  heartbeat: partialConnectionSchema,
  snapshot: snapshotSchema,
  mode_state: partialMotionSchema,
  chassis_state: partialMotionSchema,
  power_state: partialPowerSchema,
  vision_target: partialVisionSchema,
  vision_qrcode: z.object({ qrcodeText: z.string().nullable().optional(), detectTimestamp: z.string().nullable().optional() }),
  voice_cmd: partialVoiceSchema,
  task_event: partialTaskSchema,
  fault_event: partialFaultSchema,
  system_log: logSchema,
  command_ack: z.object({ commandId: z.string().min(1), status: commandStatusSchema, lifecycleStatus: commandLifecycleStatusSchema.optional(), message: z.string().optional(), detail: z.string().optional() })
};

const inboundTypeSchema = z.enum(['heartbeat', 'snapshot', 'mode_state', 'chassis_state', 'power_state', 'vision_target', 'vision_qrcode', 'voice_cmd', 'task_event', 'fault_event', 'system_log', 'command_ack']);

export type ParseInboundResult =
  | { ok: true; event: BridgeInboundEvent }
  | { ok: false; reason: string };

export function parseInboundEvent(raw: unknown): ParseInboundResult {
  const env = envelopeBase.safeParse(raw);
  if (!env.success) {
    if (typeof raw === 'object' && raw !== null && 'type' in raw && 'payload' in raw) {
      const legacyType = inboundTypeSchema.safeParse((raw as { type?: unknown }).type);
      if (!legacyType.success) return { ok: false, reason: 'legacy type 无效' };
      const parsedPayload = payloadSchemas[legacyType.data].safeParse((raw as { payload?: unknown }).payload);
      if (!parsedPayload.success) return { ok: false, reason: parsedPayload.error.issues.map((issue) => issue.path.join('.') || issue.message).join('; ') };
      return {
        ok: true,
        event: {
          eventId: `legacy-${Math.random().toString(36).slice(2, 10)}`,
          type: legacyType.data,
          ts: new Date().toISOString(),
          source: 'bridge',
          sessionId: 'legacy-session',
          seq: 0,
          payload: parsedPayload.data,
          protocolVersion: '3.0.0',
          schemaVersion: 'legacy',
          origin: 'legacy-bridge'
        } as BridgeInboundEvent
      };
    }
    return { ok: false, reason: env.error.issues.map((issue) => issue.path.join('.') || issue.message).join('; ') };
  }

  const typeResult = inboundTypeSchema.safeParse(env.data.type);
  if (!typeResult.success) return { ok: false, reason: 'event.type 无效' };
  const parsedPayload = payloadSchemas[typeResult.data].safeParse(env.data.payload);
  if (!parsedPayload.success) return { ok: false, reason: parsedPayload.error.issues.map((issue) => issue.path.join('.') || issue.message).join('; ') };

  return {
    ok: true,
    event: {
      ...env.data,
      type: typeResult.data,
      payload: parsedPayload.data
    } as BridgeInboundEvent
  };
}

export function validateOutboundEvent(raw: unknown): raw is BridgeOutboundEvent {
  return envelopeBase.safeParse(raw).success;
}
