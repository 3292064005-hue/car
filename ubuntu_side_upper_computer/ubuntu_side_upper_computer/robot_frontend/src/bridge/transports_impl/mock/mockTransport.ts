import { createLegacyEvent } from '@/bridge/protocol';
import { BRIDGE_CAPABILITIES, DEFAULT_WAYPOINTS, PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';
import { clamp, uuid } from '@/shared/utils';
import type { BridgeOutboundEvent } from '@/types/robot';
import type { BridgeTransport, MockState, TransportHandlers } from '@/bridge/transports_impl/types';
import { triggerScenario } from './scenarios';

export class MockTransport implements BridgeTransport {
  readonly label = 'mock-transport';
  readonly type = 'mock' as const;
  private handlers: TransportHandlers | null = null;
  private timer: number | null = null;
  private heartbeatTimer: number | null = null;
  private state: MockState = {
    mode: 'BOOT',
    battery: 82,
    voltage: 11.9,
    currentWaypoint: null,
    progress: 0,
    completedPoints: 0,
    params: {
      maxLinearSpeed: 0.45,
      maxAngularSpeed: 1.1,
      teleopStep: 0.08,
      trackOffsetDeadband: 0.1,
      lowPowerThreshold: 25,
      reconnectTimeoutMs: 1500,
    },
    estop: false,
    safeStop: false,
    faultLock: false,
    dropHeartbeatUntil: 0,
    ackTimeoutNext: false,
  };

  connect(handlers: TransportHandlers): void {
    this.handlers = handlers;
    this.handlers.onOpen();
    this.handlers.onMessage(
      createLegacyEvent('snapshot', {
        connection: {
          rosConnected: true,
          bridgeConnected: true,
          stm32Connected: true,
          videoConnected: true,
          voiceConnected: true,
          reconnecting: false,
          latencyMs: 32,
          heartbeatAgeMs: 0,
          lastHeartbeatAt: new Date().toISOString(),
          transportLabel: this.label,
          transportType: 'mock',
          reconnectAttempts: 0,
          staleMotion: false,
          stalePower: false,
          staleVision: false,
          staleVoice: false,
          inboundRateHz: 0,
          outboundRateHz: 0,
          protocolVersion: PROTOCOL_VERSION,
          schemaVersion: SCHEMA_VERSION,
          capabilities: BRIDGE_CAPABILITIES,
          lastSnapshotVersion: SCHEMA_VERSION,
          lastTraceId: null,
          compatibilityMode: 'legacy-v3',
        },
        motion: { mode: 'IDLE', lastUpdateAt: new Date().toISOString() },
        power: { batteryPercent: 82, batteryVoltage: 11.9, lowPowerWarning: false, charging: false, lastUpdateAt: new Date().toISOString() },
        vision: { targetType: 'marker', detectTimestamp: new Date().toISOString(), trackingReady: true },
        voice: { wakeStatus: 'idle', recentCommands: [] },
        task: { totalPoints: 4, completedPoints: 0, progress: 0, patrolStatus: 'idle', waypoints: DEFAULT_WAYPOINTS },
        fault: { level: 'info', code: null, message: null, safeStopActive: false, estopActive: false, timeoutStopActive: false, lastUpdateAt: new Date().toISOString() },
        params: this.state.params,
        logs: [],
      }),
    );

    this.state.mode = 'IDLE';
    this.timer = window.setInterval(() => this.emitTelemetry(), 900);
    this.heartbeatTimer = window.setInterval(() => {
      if (Date.now() < this.state.dropHeartbeatUntil) return;
      this.handlers?.onMessage(
        createLegacyEvent('heartbeat', {
          bridgeConnected: true,
          rosConnected: true,
          stm32Connected: true,
          videoConnected: true,
          voiceConnected: true,
          latencyMs: 24 + Math.round(Math.random() * 28),
        }),
      );
    }, 700);
  }

  disconnect(): void {
    if (this.timer) window.clearInterval(this.timer);
    if (this.heartbeatTimer) window.clearInterval(this.heartbeatTimer);
    this.handlers?.onClose();
  }

  send(event: BridgeOutboundEvent): void {
    if (!this.state.ackTimeoutNext) {
      window.setTimeout(() => {
        this.handlers?.onMessage(createLegacyEvent('command_ack', { commandId: event.eventId, status: 'ack', message: `已受理 ${event.type}` }));
      }, 40);
    } else {
      this.state.ackTimeoutNext = false;
    }
    window.setTimeout(() => this.applyCommand(event), 120);
  }

  triggerLocalScenario(scenarioId: string): void {
    triggerScenario(this.state, this.handlers, scenarioId);
  }

  private emitTelemetry(): void {
    const moving = ['MANUAL', 'PATROL', 'TRACK'].includes(this.state.mode) && !this.state.safeStop && !this.state.estop;
    const now = new Date().toISOString();
    const linear = moving ? Number((0.09 + Math.random() * 0.12).toFixed(2)) : 0;
    const angular = moving ? Number((Math.random() * 0.6 - 0.3).toFixed(2)) : 0;

    this.state.battery = clamp(Number((this.state.battery - 0.05).toFixed(2)), 12, 100) as number;
    this.state.voltage = Number((11.2 + Math.random() * 0.45).toFixed(2));

    this.handlers?.onMessage(
      createLegacyEvent('chassis_state', {
        linearVelocity: linear,
        angularVelocity: angular,
        leftWheelSpeed: Number((linear - angular * 0.15).toFixed(2)),
        rightWheelSpeed: Number((linear + angular * 0.15).toFixed(2)),
        odomX: Number((moving ? Math.random() * 3.5 : Math.random()).toFixed(2)),
        odomY: Number((moving ? Math.random() * 1.3 : 0).toFixed(2)),
        odomYaw: Number((angular * 0.3).toFixed(2)),
        isManualOverride: this.state.mode === 'MANUAL',
        commandSource: this.state.mode === 'PATROL' ? 'task' : this.state.mode === 'TRACK' ? 'bridge' : 'ui',
        lastUpdateAt: now,
        mode: this.state.mode,
      }),
    );

    this.handlers?.onMessage(createLegacyEvent('power_state', { batteryPercent: this.state.battery, batteryVoltage: this.state.voltage, lowPowerWarning: this.state.battery <= this.state.params.lowPowerThreshold, charging: false, lastUpdateAt: now }));
    this.handlers?.onMessage(createLegacyEvent('vision_target', { targetType: moving ? 'inspection-marker' : 'idle-view', targetOffsetX: Number((Math.random() * 0.8 - 0.4).toFixed(2)), targetOffsetY: Number((Math.random() * 0.4 - 0.2).toFixed(2)), detectTimestamp: now, trackingReady: true, frameDrops: Math.floor(Math.random() * 4), lastUpdateAt: now }));

    if (Math.random() > 0.72) {
      const command = ['开始巡检', '停止巡检', '进入待机', '左转', '右转'][Math.floor(Math.random() * 5)];
      this.handlers?.onMessage(createLegacyEvent('voice_cmd', { lastVoiceCommand: command, voiceConfidence: Number((0.78 + Math.random() * 0.17).toFixed(2)), speaking: false, lastSpeakText: '系统状态正常', wakeStatus: 'triggered', lastUpdateAt: now }));
    }

    if (this.state.mode === 'PATROL') {
      this.state.progress = clamp(Number((this.state.progress + 0.1).toFixed(2)), 0, 1) as number;
      this.state.completedPoints = Math.min(4, Math.max(this.state.completedPoints, Math.round(this.state.progress * 4)));
      this.state.currentWaypoint = DEFAULT_WAYPOINTS[Math.min(3, this.state.completedPoints)]?.id ?? 'P4';
      this.handlers?.onMessage(
        createLegacyEvent('task_event', {
          patrolStatus: this.state.progress >= 1 ? 'completed' : 'running',
          currentWaypoint: this.state.currentWaypoint,
          progress: this.state.progress,
          completedPoints: this.state.completedPoints,
          totalPoints: 4,
          trackEnabled: false,
          lastTaskEvent: now,
          waypoints: DEFAULT_WAYPOINTS.map((point, index) => ({ ...point, status: index < this.state.completedPoints ? 'done' : point.id === this.state.currentWaypoint ? 'running' : 'pending' })),
        }),
      );
      if (this.state.progress >= 1) this.state.mode = 'IDLE';
    }
  }

  private applyCommand(event: BridgeOutboundEvent): void {
    const now = new Date().toISOString();
    const log = (message: string, domain: 'CONTROL' | 'SAFETY' | 'TASK' | 'PARAM' | 'VOICE' = 'CONTROL') => {
      this.handlers?.onMessage(createLegacyEvent('system_log', { id: uuid('log'), timestamp: now, level: domain === 'SAFETY' ? 'ERROR' : 'INFO', domain, message }));
    };

    switch (event.type) {
      case 'set_mode':
        this.state.mode = event.payload.mode;
        this.handlers?.onMessage(createLegacyEvent('mode_state', { mode: event.payload.mode, isManualOverride: event.payload.mode === 'MANUAL', lastUpdateAt: now }));
        log(`模式切换为 ${event.payload.mode}`);
        break;
      case 'teleop_cmd':
        this.state.mode = 'MANUAL';
        this.handlers?.onMessage(createLegacyEvent('chassis_state', { mode: 'MANUAL', isManualOverride: true, linearVelocity: event.payload.linear, angularVelocity: event.payload.angular, leftWheelSpeed: Number((event.payload.linear - event.payload.angular * 0.15).toFixed(2)), rightWheelSpeed: Number((event.payload.linear + event.payload.angular * 0.15).toFixed(2)), commandSource: 'ui', lastUpdateAt: now }));
        break;
      case 'stop_now':
        this.handlers?.onMessage(createLegacyEvent('chassis_state', { linearVelocity: 0, angularVelocity: 0, leftWheelSpeed: 0, rightWheelSpeed: 0, lastUpdateAt: now }));
        log('已执行立即停车命令');
        break;
      case 'estop':
        this.state.estop = true;
        this.state.safeStop = true;
        this.state.mode = 'SAFE_STOP';
        this.handlers?.onMessage(createLegacyEvent('fault_event', { level: 'critical', code: 'ESTOP', message: '前端触发急停', estopActive: true, safeStopActive: true, timeoutStopActive: false, lastUpdateAt: now }));
        this.handlers?.onMessage(createLegacyEvent('mode_state', { mode: 'SAFE_STOP', lastUpdateAt: now }));
        log('急停已触发', 'SAFETY');
        break;
      case 'resume_from_safe_stop':
        this.state.estop = false;
        this.state.safeStop = false;
        this.state.faultLock = false;
        this.state.mode = 'IDLE';
        this.handlers?.onMessage(createLegacyEvent('fault_event', { level: 'info', code: null, message: '安全停车已解除', estopActive: false, safeStopActive: false, timeoutStopActive: false, lastUpdateAt: now }));
        this.handlers?.onMessage(createLegacyEvent('mode_state', { mode: 'IDLE', lastUpdateAt: now }));
        log('已从 SAFE_STOP 恢复到 IDLE', 'SAFETY');
        break;
      case 'start_patrol':
        this.state.mode = 'PATROL';
        this.state.progress = 0.25;
        this.state.completedPoints = 1;
        this.state.currentWaypoint = 'P2';
        this.handlers?.onMessage(createLegacyEvent('task_event', { patrolStatus: 'running', currentWaypoint: 'P2', progress: 0.25, completedPoints: 1, totalPoints: 4, lastTaskEvent: now, waypoints: DEFAULT_WAYPOINTS.map((point, index) => ({ ...point, status: index === 0 ? 'done' : index === 1 ? 'running' : 'pending' })) }));
        this.handlers?.onMessage(createLegacyEvent('mode_state', { mode: 'PATROL', lastUpdateAt: now }));
        log('巡检任务已开始', 'TASK');
        break;
      case 'pause_patrol':
        this.handlers?.onMessage(createLegacyEvent('task_event', { patrolStatus: 'paused', lastTaskEvent: now }));
        log('巡检任务已暂停', 'TASK');
        break;
      case 'stop_patrol':
        this.state.mode = 'IDLE';
        this.state.progress = 0;
        this.state.completedPoints = 0;
        this.state.currentWaypoint = null;
        this.handlers?.onMessage(createLegacyEvent('task_event', { patrolStatus: 'aborted', currentWaypoint: null, progress: 0, completedPoints: 0, totalPoints: 4, lastTaskEvent: now, waypoints: DEFAULT_WAYPOINTS }));
        this.handlers?.onMessage(createLegacyEvent('mode_state', { mode: 'IDLE', lastUpdateAt: now }));
        log('巡检任务已停止', 'TASK');
        break;
      case 'set_param':
        this.state.params = { ...this.state.params, [event.payload.key]: event.payload.value };
        log(`参数 ${event.payload.key} 已更新为 ${event.payload.value}`, 'PARAM');
        break;
      case 'apply_param_profile':
        log(`已请求应用参数配置 ${event.payload.profileName}`, 'PARAM');
        break;
      case 'speak_fixed_text':
        this.handlers?.onMessage(createLegacyEvent('voice_cmd', { speaking: true, lastSpeakText: event.payload.text, lastVoiceCommand: '手动播报', voiceConfidence: 1, lastUpdateAt: now }));
        window.setTimeout(() => {
          this.handlers?.onMessage(createLegacyEvent('voice_cmd', { speaking: false, lastSpeakText: event.payload.text, lastUpdateAt: new Date().toISOString() }));
        }, 900);
        log(`播报文本：${event.payload.text}`, 'VOICE');
        break;
      default:
        break;
    }
  }
}
