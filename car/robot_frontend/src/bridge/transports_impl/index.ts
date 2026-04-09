import { ENABLE_MOCK, WS_URL } from '@/shared/constants';
import { MockTransport } from './mock/mockTransport';
import { WebSocketTransport } from './websocketTransport';
import type { BridgeTransport } from './types';

export type { BridgeTransport, TransportHandlers } from './types';

function shouldUseMockTransport(): boolean {
  const trimmedWebsocketUrl = WS_URL.trim();
  return ENABLE_MOCK && trimmedWebsocketUrl.length === 0;
}

export function createTransport(): BridgeTransport {
  return shouldUseMockTransport() ? new MockTransport() : new WebSocketTransport();
}
