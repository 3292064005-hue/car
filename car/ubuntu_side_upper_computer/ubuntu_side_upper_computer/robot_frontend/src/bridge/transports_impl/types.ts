import type { BridgeOutboundEvent, ParamProfile, RobotMode } from '@/types/robot';

export interface TransportHandlers {
  onOpen: () => void;
  onClose: () => void;
  onError: (message: string) => void;
  onMessage: (message: unknown) => void;
}

export interface BridgeTransport {
  readonly label: string;
  readonly type: 'mock' | 'websocket';
  connect: (handlers: TransportHandlers) => void;
  disconnect: () => void;
  send: (event: BridgeOutboundEvent) => void;
  triggerLocalScenario?: (scenarioId: string) => void;
}

export interface MockState {
  mode: RobotMode;
  battery: number;
  voltage: number;
  currentWaypoint: string | null;
  progress: number;
  completedPoints: number;
  params: ParamProfile;
  estop: boolean;
  safeStop: boolean;
  faultLock: boolean;
  dropHeartbeatUntil: number;
  ackTimeoutNext: boolean;
}
