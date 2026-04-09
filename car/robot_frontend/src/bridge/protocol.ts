import { BRIDGE_CAPABILITIES, COMMAND_TIMEOUT_MS, DANGEROUS_COMMANDS, PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';
import { uuid } from '@/shared/utils';
import type { BridgeOutboundEvent, BridgeOutboundPayloadMap, CommandType, EventEnvelope, SourceType } from '@/types/robot';

export function createEnvelope<TType extends CommandType>(input: {
  type: TType;
  payload: BridgeOutboundPayloadMap[TType];
  sessionId: string;
  seq: number;
  source?: SourceType;
  reason?: string;
  dedupeKey?: string;
}): BridgeOutboundEvent {
  return {
    eventId: uuid('cmd'),
    type: input.type,
    ts: new Date().toISOString(),
    source: input.source ?? 'frontend',
    sessionId: input.sessionId,
    seq: input.seq,
    payload: input.payload,
    protocolVersion: PROTOCOL_VERSION,
    schemaVersion: SCHEMA_VERSION,
    capabilities: [...BRIDGE_CAPABILITIES],
    compatibilityMode: 'native-v4',
    traceId: uuid('trace'),
    origin: 'robot-console-v4',
    dedupeKey: input.dedupeKey,
    retryPolicy: input.type === 'teleop_cmd' ? 'never' : 'once',
    priority: input.type === 'estop' ? 'critical' : DANGEROUS_COMMANDS.includes(input.type) ? 'high' : 'normal',
    requireAck: true,
    ttlMs: COMMAND_TIMEOUT_MS,
    dangerous: DANGEROUS_COMMANDS.includes(input.type),
    operator: 'frontend-console',
    reason: input.reason
  } as BridgeOutboundEvent;
}

export function createLegacyEvent<TType extends string, TPayload>(type: TType, payload: TPayload): EventEnvelope<TType, TPayload> {
  return {
    eventId: uuid('evt'),
    type,
    ts: new Date().toISOString(),
    source: 'mock',
    sessionId: 'mock-session',
    seq: 0,
    payload,
    protocolVersion: '3.0.0',
    schemaVersion: 'legacy',
    origin: 'mock-transport'
  };
}
