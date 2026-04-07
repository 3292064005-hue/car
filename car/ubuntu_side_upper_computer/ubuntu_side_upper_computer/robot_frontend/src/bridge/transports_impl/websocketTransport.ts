import { WS_URL } from '@/shared/constants';
import type { BridgeOutboundEvent } from '@/types/robot';
import type { BridgeTransport, TransportHandlers } from './types';

export class WebSocketTransport implements BridgeTransport {
  readonly label = WS_URL;
  readonly type = 'websocket' as const;
  private socket: WebSocket | null = null;
  private handlers: TransportHandlers | null = null;
  private reconnectTimer: number | null = null;
  private manualClose = false;
  private attempt = 0;

  connect(handlers: TransportHandlers): void {
    this.handlers = handlers;
    this.manualClose = false;
    this.open();
  }

  private scheduleReconnect(): void {
    if (this.manualClose) return;
    const backoff = Math.min(8000, 600 * 2 ** this.attempt);
    const jitter = Math.round(Math.random() * 250);
    const wait = backoff + jitter;
    this.reconnectTimer = window.setTimeout(() => this.open(), wait);
  }

  private open(): void {
    this.socket = new WebSocket(WS_URL);
    this.socket.onopen = () => {
      this.attempt = 0;
      this.handlers?.onOpen();
    };
    this.socket.onmessage = (event) => this.handlers?.onMessage(event.data);
    this.socket.onerror = () => this.handlers?.onError('桥接层连接异常。');
    this.socket.onclose = () => {
      this.handlers?.onClose();
      this.attempt += 1;
      this.scheduleReconnect();
    };
  }

  disconnect(): void {
    this.manualClose = true;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.socket = null;
  }

  send(event: BridgeOutboundEvent): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.handlers?.onError('命令发送失败：bridge 未连接。');
      return;
    }
    this.socket.send(JSON.stringify(event));
  }
}
