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
  activeProfileName: string;
  runtimeParamVersion: number;
  committedParams: ParamProfile;
  committedProfileName: string;
  committedRuntimeParamVersion: number;
  lastParamApplyResult?: {
    ok?: boolean;
    message?: string;
    ts?: string;
    reason?: string;
    traceId?: string;
    transactionId?: string;
    state?: 'pending' | 'applied' | 'failed' | 'timeout';
    rollbackPerformed?: boolean;
  } | null;
  lastTransaction?: {
    transactionId: string;
    ackMode: string;
    expectedConsumers: string[];
    consumerStatuses: Record<string, { consumer: string; ok?: boolean | null; message?: string; state?: 'pending' | 'applied' | 'failed' | 'timeout'; ts?: string; traceId?: string }>;
    deadlineTs?: string | null;
    startedAt?: string | null;
    completedAt?: string | null;
    state?: 'pending' | 'applied' | 'failed' | 'timeout';
  } | null;
  estop: boolean;
  safeStop: boolean;
  faultLock: boolean;
  dropHeartbeatUntil: number;
  ackTimeoutNext: boolean;
}
