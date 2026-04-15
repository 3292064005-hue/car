import { z } from 'zod';
import {
  COMMAND_TYPES,
  COMPATIBILITY_MODES,
  inboundPayloadSchemas,
  inboundTypeSchema,
  outboundPayloadSchemas,
  sourceSchema,
} from '@/generated/bridgeContract';
import { PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';
import type { BridgeInboundEvent, BridgeOutboundEvent } from '@/types/robot';

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

const formatIssues = (issues: z.ZodIssue[]): string => issues.map((issue) => issue.path.join('.') || issue.message).join('; ');

export type ParseInboundResult =
  | { ok: true; event: BridgeInboundEvent }
  | { ok: false; reason: string };

export function parseInboundEvent(raw: unknown): ParseInboundResult {
  const env = envelopeBase.safeParse(raw);
  if (!env.success) {
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
      compatibilityMode: 'native-v4',
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
