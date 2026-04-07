import { ENABLE_MOCK } from '@/shared/constants';
import { MockTransport } from './mock/mockTransport';
import { WebSocketTransport } from './websocketTransport';
import type { BridgeTransport } from './types';

export type { BridgeTransport, TransportHandlers } from './types';

export function createTransport(): BridgeTransport {
  return ENABLE_MOCK ? new MockTransport() : new WebSocketTransport();
}
