import { createLegacyEvent } from '@/bridge/protocol';
import { DEFAULT_WAYPOINTS } from '@/shared/constants';
import { uuid } from '@/shared/utils';
import type { MockState, TransportHandlers } from '@/bridge/transports_impl/types';

export function triggerScenario(state: MockState, handlers: TransportHandlers | null, scenarioId: string): void {
  const now = new Date().toISOString();
  switch (scenarioId) {
    case 'low-power':
      state.battery = 16;
      state.voltage = 10.7;
      handlers?.onMessage(createLegacyEvent('power_state', { batteryPercent: 16, batteryVoltage: 10.7, lowPowerWarning: true, charging: false, lastUpdateAt: now }));
      handlers?.onMessage(createLegacyEvent('system_log', { id: uuid('log'), timestamp: now, level: 'WARN', domain: 'SAFETY', message: '已注入低压场景' }));
      break;
    case 'heartbeat-drop':
      state.dropHeartbeatUntil = Date.now() + 4200;
      handlers?.onMessage(createLegacyEvent('system_log', { id: uuid('log'), timestamp: now, level: 'WARN', domain: 'BRIDGE', message: '已注入心跳中断场景' }));
      break;
    case 'fault-lock':
      state.faultLock = true;
      state.mode = 'FAULT';
      handlers?.onMessage(createLegacyEvent('fault_event', { level: 'critical', code: 'DRV_FAULT', message: '模拟驱动器故障锁定', estopActive: false, safeStopActive: true, timeoutStopActive: false, lastUpdateAt: now }));
      handlers?.onMessage(createLegacyEvent('mode_state', { mode: 'FAULT', lastUpdateAt: now }));
      break;
    case 'ack-timeout':
      state.ackTimeoutNext = true;
      handlers?.onMessage(createLegacyEvent('system_log', { id: uuid('log'), timestamp: now, level: 'WARN', domain: 'BRIDGE', message: '下一个命令 ACK 将超时' }));
      break;
    case 'patrol-interrupt':
      state.mode = 'IDLE';
      handlers?.onMessage(createLegacyEvent('task_event', { patrolStatus: 'aborted', currentWaypoint: 'P3', progress: 0.56, completedPoints: 2, totalPoints: 4, lastTaskEvent: now, waypoints: DEFAULT_WAYPOINTS.map((point, index) => ({ ...point, status: index < 2 ? 'done' : point.id === 'P3' ? 'failed' : 'pending', note: point.id === 'P3' ? '前方障碍' : undefined })) }));
      handlers?.onMessage(createLegacyEvent('system_log', { id: uuid('log'), timestamp: now, level: 'ERROR', domain: 'TASK', message: '已注入巡检中断场景' }));
      break;
    case 'qr-burst':
      ['柜门-02', '泵站-A', '阀门-C3'].forEach((label, index) => {
        window.setTimeout(() => {
          handlers?.onMessage(createLegacyEvent('vision_qrcode', { qrcodeText: label, detectTimestamp: new Date().toISOString() }));
        }, index * 220);
      });
      break;
    case 'estop-latch':
      state.estop = true;
      state.safeStop = true;
      state.mode = 'SAFE_STOP';
      handlers?.onMessage(createLegacyEvent('fault_event', { level: 'critical', code: 'ESTOP', message: '模拟急停锁定', estopActive: true, safeStopActive: true, timeoutStopActive: false, lastUpdateAt: now }));
      handlers?.onMessage(createLegacyEvent('mode_state', { mode: 'SAFE_STOP', lastUpdateAt: now }));
      break;
    case 'voice-burst':
      ['开始巡检', '停车', '左转', '回到待机'].forEach((command, index) => {
        window.setTimeout(() => {
          handlers?.onMessage(createLegacyEvent('voice_cmd', { lastVoiceCommand: command, voiceConfidence: Number((0.7 + Math.random() * 0.25).toFixed(2)), speaking: false, lastSpeakText: null, wakeStatus: 'triggered', lastUpdateAt: new Date().toISOString() }));
        }, index * 180);
      });
      break;
    default:
      break;
  }
}
