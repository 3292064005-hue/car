import { z } from 'zod';
import {
  commandLifecycleStatusSchema,
  commandAckStatusSchema,
  COMMAND_TYPES,
  COMPATIBILITY_MODES,
  inboundPayloadSchemas,
  inboundTypeSchema,
  outboundPayloadSchemas,
  sourceSchema,
} from '@/generated/bridgeContract';
import { PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';
import type { BridgeInboundEvent, BridgeLegacyInboundEvent, BridgeOutboundEvent, InboundEventType } from '@/types/robot';

const compatibilityModeSchema = z.enum(COMPATIBILITY_MODES);

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
  compatibilityMode: compatibilityModeSchema.optional(),
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
  retryPolicy: z.enum(['never', 'once', 'aggressive']).optional(),
});

const legacyCommandAckPayloadSchema = z.object({
  commandId: z.string().min(1),
  status: commandAckStatusSchema,
  lifecycleStatus: commandLifecycleStatusSchema.optional(),
  message: z.string().optional(),
  detail: z.string().optional(),
});

const legacyPayloadSchemas: Record<InboundEventType, z.ZodTypeAny> = {
  ...inboundPayloadSchemas,
  command_ack: legacyCommandAckPayloadSchema,
};

const formatIssues = (issues: z.ZodIssue[]): string => issues.map((issue) => issue.path.join('.') || issue.message).join('; ');

export type ParseInboundResult =
  | { ok: true; event: BridgeInboundEvent }
  | { ok: false; reason: string };

export function parseInboundEvent(raw: unknown): ParseInboundResult {
  const env = envelopeBase.safeParse(raw);
  if (!env.success) {
    if (typeof raw === 'object' && raw !== null && 'type' in raw && 'payload' in raw) {
      const legacyType = inboundTypeSchema.safeParse((raw as { type?: unknown }).type);
      if (!legacyType.success) return { ok: false, reason: 'legacy type 无效' };
      const parsedPayload = legacyPayloadSchemas[legacyType.data].safeParse((raw as BridgeLegacyInboundEvent).payload);
      if (!parsedPayload.success) return { ok: false, reason: formatIssues(parsedPayload.error.issues) };
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
          origin: 'legacy-bridge',
        } as BridgeInboundEvent,
      };
    }
    return { ok: false, reason: formatIssues(env.error.issues) };
  }

  const typeResult = inboundTypeSchema.safeParse(env.data.type);
  if (!typeResult.success) return { ok: false, reason: 'event.type 无效' };
  const parsedPayload = inboundPayloadSchemas[typeResult.data].safeParse(env.data.payload);
  if (!parsedPayload.success) return { ok: false, reason: formatIssues(parsedPayload.error.issues) };

  return {
    ok: true,
    event: {
      ...env.data,
      type: typeResult.data,
      payload: parsedPayload.data,
    } as BridgeInboundEvent,
  };
}

export function validateOutboundEvent(raw: unknown): raw is BridgeOutboundEvent {
  const env = envelopeBase.safeParse(raw);
  if (!env.success) return false;
  const typeResult = z.enum(COMMAND_TYPES).safeParse(env.data.type);
  if (!typeResult.success) return false;
  return outboundPayloadSchemas[typeResult.data].safeParse(env.data.payload).success;
}
