import { parseInboundEvent, validateOutboundEvent } from '@/bridge/guards';
import { prepareOutboundCommand } from '@/bridge/commandPolicy';
import { summarizeInspectorRaw } from '@/shared/utils';
import type { BridgeTransport } from '@/bridge/transports';
import type { BridgeOutboundPayloadMap, CommandType } from '@/types/robot';
import type { RobotStore } from '@/store/model';

export function handleInboundBridgePayload(raw: unknown, store: RobotStore): void {
  const rawText = summarizeInspectorRaw(raw);
  let parsed: unknown = raw;
  if (typeof raw === 'string') {
    try {
      parsed = JSON.parse(raw) as unknown;
    } catch {
      store.recordTrace('rejected', 'json', rawText, 'rejected', '收到无法解析的 bridge JSON 数据');
      store.pushLog({ level: 'WARN', domain: 'BRIDGE', message: '收到无法解析的 bridge JSON 数据。' });
      return;
    }
  }

  const result = parseInboundEvent(parsed);
  if (!result.ok) {
    const type = typeof parsed === 'object' && parsed !== null && 'type' in parsed ? String((parsed as { type?: unknown }).type ?? 'unknown') : 'unknown';
    store.recordTrace('rejected', type, rawText, 'rejected', result.reason);
    store.pushLog({ level: 'WARN', domain: 'BRIDGE', message: 'bridge 消息未通过前端运行时校验，已丢弃。', details: result.reason });
    return;
  }

  store.recordTrace('in', result.event.type, rawText, 'accepted');
  store.applyInboundEvent(result.event);
}

export function dispatchOutboundBridgeCommand<TType extends CommandType>(
  transport: BridgeTransport | null,
  store: RobotStore,
  type: TType,
  payload: BridgeOutboundPayloadMap[TType],
  summary: string,
  seq: number,
): void {
  const prepared = prepareOutboundCommand(type, payload, summary, seq);
  if (!prepared) return;
  if (!validateOutboundEvent(prepared.envelope)) {
    store.setRuntimeRejection('出站命令未通过前端协议校验。');
    return;
  }
  if (!transport) {
    store.markCommand(prepared.envelope.eventId, 'rejected', 'bridge 尚未初始化');
    return;
  }
  transport.send(prepared.envelope);
  store.markCommandSent(prepared.envelope.eventId);
}
