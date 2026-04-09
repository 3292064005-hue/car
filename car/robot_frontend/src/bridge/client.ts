import { createTransport, type BridgeTransport } from '@/bridge/transports';
import { BRIDGE_LABEL } from '@/shared/constants';
import { useRobotStore } from '@/store/useRobotStore';
import type { BridgeOutboundPayloadMap, CommandType } from '@/types/robot';
import { dispatchOutboundBridgeCommand, handleInboundBridgePayload } from '@/bridge/appService';

class RobotBridgeClient {
  private transport: BridgeTransport | null = null;
  private seq = 0;

  connect(): void {
    if (this.transport) return;
    this.transport = createTransport();
    useRobotStore.getState().setTransportInfo(this.transport.type, this.transport.label || BRIDGE_LABEL);

    this.transport.connect({
      onOpen: () => {
        useRobotStore.getState().markBridgeOpen();
      },
      onClose: () => {
        useRobotStore.getState().markBridgeClosed();
      },
      onError: (message) => {
        useRobotStore.getState().pushLog({ level: 'ERROR', domain: 'BRIDGE', message });
      },
      onMessage: (raw) => {
        handleInboundBridgePayload(raw, useRobotStore.getState());
      },
    });
  }

  disconnect(): void {
    this.transport?.disconnect();
    this.transport = null;
  }

  runLocalScenario(id: string): void {
    if (!this.transport?.triggerLocalScenario) {
      useRobotStore.getState().pushLog({ level: 'WARN', domain: 'INSPECTOR', message: '当前 transport 不支持本地场景注入。' });
      return;
    }
    this.transport.triggerLocalScenario(id);
    useRobotStore.getState().pushLog({ level: 'INFO', domain: 'INSPECTOR', message: `已注入本地场景：${id}` });
  }

  send<TType extends CommandType>(type: TType, payload: BridgeOutboundPayloadMap[TType], summary: string): void {
    dispatchOutboundBridgeCommand(this.transport, useRobotStore.getState(), type, payload, summary, ++this.seq);
  }
}

export const robotBridge = new RobotBridgeClient();
