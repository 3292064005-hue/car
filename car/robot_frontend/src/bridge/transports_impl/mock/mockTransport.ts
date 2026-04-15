import { createMockInboundEvent } from '@/bridge/protocol';
import { BRIDGE_CAPABILITIES, DEFAULT_WAYPOINTS, PARAM_PRESETS, PROTOCOL_VERSION, SCHEMA_VERSION } from '@/shared/constants';
import { clamp, deepCloneParams, uuid } from '@/shared/utils';
import type { BridgeOutboundEvent } from '@/types/robot';
import type { BridgeTransport, MockState, TransportHandlers } from '@/bridge/transports_impl/types';
import { triggerScenario } from './scenarios';

const PARAM_TRANSACTION_CONSUMERS = ['robot_control', 'robot_decision', 'robot_monitor'] as const;

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
    params: deepCloneParams(PARAM_PRESETS['演示标准']),
    activeProfileName: '演示标准',
    runtimeParamVersion: 1,
    committedParams: deepCloneParams(PARAM_PRESETS['演示标准']),
    committedProfileName: '演示标准',
    committedRuntimeParamVersion: 1,
    lastParamApplyResult: {
      ok: true,
      message: 'defaults_loaded',
      ts: new Date().toISOString(),
      state: 'applied',
      rollbackPerformed: false,
    },
    lastTransaction: null,
    estop: false,
    safeStop: false,
    faultLock: false,
    dropHeartbeatUntil: 0,
    ackTimeoutNext: false,
  };

  connect(handlers: TransportHandlers): void {
    this.handlers = handlers;
    this.handlers.onOpen();
    this.emitSnapshot();

    this.state.mode = 'IDLE';
    this.timer = window.setInterval(() => this.emitTelemetry(), 900);
    this.heartbeatTimer = window.setInterval(() => {
      if (Date.now() < this.state.dropHeartbeatUntil) return;
      this.handlers?.onMessage(
        createMockInboundEvent('heartbeat', {
          bridgeConnected: true,
          rosConnected: true,
          stm32Connected: true,
          videoConnected: true,
          voiceConnected: true,
          latencyMs: 24 + Math.round(Math.random() * 28),
          wifiTransportReady: true,
          uartBoardReady: true,
          motionHeartbeatReady: true,
          commandLinkReady: true,
          gatewayReady: true,
          gatewayReadyReasons: ['mock_transport_ready'],
          gatewayReadyTopic: '/robot/web_bridge/ready',
          operatorSurfaceReady: true,
          operatorSurfaceReadyReasons: ['mock_transport_ready'],
          operatorSurfaceReadyTopic: '/robot/api/health',
          operatorReady: true,
          operatorReadyReasons: ['mock_transport_ready'],
          operatorReadyTopic: '/robot/api/health',
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
        this.handlers?.onMessage(
          createMockInboundEvent('command_ack', {
            commandId: event.eventId,
            status: 'ack',
            lifecycleStatus: 'accepted',
            message: `已受理 ${event.type}`,
            traceId: event.traceId,
          }),
        );
      }, 40);
    } else {
      this.state.ackTimeoutNext = false;
    }
    window.setTimeout(() => this.applyCommand(event), 120);
  }

  triggerLocalScenario(scenarioId: string): void {
    triggerScenario(this.state, this.handlers, scenarioId);
  }

  private emitSnapshot(): void {
    const now = new Date().toISOString();
    const transaction = this.state.lastTransaction;
    const projectionState = transaction?.transactionId && transaction.state === 'pending' ? 'provisional' : 'committed';
    this.handlers?.onMessage(
      createMockInboundEvent('snapshot', {
        connection: {
          rosConnected: true,
          bridgeConnected: true,
          stm32Connected: true,
          videoConnected: true,
          voiceConnected: true,
          reconnecting: false,
          latencyMs: 32,
          heartbeatAgeMs: 0,
          lastHeartbeatAt: now,
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
          capabilities: [...BRIDGE_CAPABILITIES],
          lastSnapshotVersion: SCHEMA_VERSION,
          lastTraceId: transaction?.consumerStatuses?.robot_monitor?.traceId ?? null,
          compatibilityMode: 'native-v4',
          runtimeHealthState: 'ready',
          runtimeHealthReasons: [],
          wifiTransportReady: true,
          uartBoardReady: true,
          motionHeartbeatReady: true,
          commandLinkReady: true,
          gatewayReady: true,
          gatewayReadyReasons: ['mock_transport_ready'],
          gatewayReadyTopic: '/robot/web_bridge/ready',
          operatorSurfaceReady: true,
          operatorSurfaceReadyReasons: ['mock_transport_ready'],
          operatorSurfaceReadyTopic: '/robot/api/health',
          operatorReady: true,
          operatorReadyReasons: ['mock_transport_ready'],
          operatorReadyTopic: '/robot/api/health',
        },
        motion: { mode: this.state.mode === 'BOOT' ? 'IDLE' : this.state.mode, lastUpdateAt: now },
        power: {
          batteryPercent: this.state.battery,
          batteryVoltage: this.state.voltage,
          lowPowerWarning: this.state.battery <= this.state.params.lowPowerThreshold,
          charging: false,
          lastUpdateAt: now,
        },
        vision: { targetType: 'marker', detectTimestamp: now, trackingReady: true },
        voice: { wakeStatus: 'idle', recentCommands: [] },
        task: {
          totalPoints: 4,
          completedPoints: this.state.completedPoints,
          progress: this.state.progress,
          patrolStatus: this.state.mode === 'PATROL' ? 'running' : 'idle',
          waypoints: DEFAULT_WAYPOINTS,
        },
        fault: {
          level: this.state.estop || this.state.safeStop ? 'critical' : 'info',
          code: this.state.estop ? 'ESTOP' : null,
          message: this.state.estop ? '前端触发急停' : null,
          safeStopActive: this.state.safeStop,
          estopActive: this.state.estop,
          timeoutStopActive: false,
          lastUpdateAt: now,
        },
        params: deepCloneParams(this.state.params),
        paramMetadata: {
          activeProfileName: this.state.activeProfileName,
          runtimeParamVersion: this.state.runtimeParamVersion,
          projectionState,
          configDigest: `mock-${this.state.runtimeParamVersion}`,
          committedConfigDigest: `mock-${this.state.committedRuntimeParamVersion}`,
          committedProfileName: this.state.committedProfileName,
          committedRuntimeParamVersion: this.state.committedRuntimeParamVersion,
          lastParamApplyResult: this.state.lastParamApplyResult,
          lastTransaction: this.state.lastTransaction,
        },
        logs: [],
      }),
    );
  }

  private beginParamTransaction(event: BridgeOutboundEvent, nextParams: MockState['params'], nextProfileName: string, reason: string): void {
    const now = new Date().toISOString();
    const nextVersion = this.state.runtimeParamVersion + 1;
    const transactionId = `mock-param-${nextVersion}-${uuid('txn').slice(-6)}`;
    this.state.params = deepCloneParams(nextParams);
    this.state.activeProfileName = nextProfileName;
    this.state.runtimeParamVersion = nextVersion;
    this.state.lastParamApplyResult = {
      ok: true,
      message: reason,
      ts: now,
      reason,
      traceId: event.traceId,
      transactionId,
      state: 'pending',
      rollbackPerformed: false,
    };
    this.state.lastTransaction = {
      transactionId,
      ackMode: 'all_consumers',
      expectedConsumers: [...PARAM_TRANSACTION_CONSUMERS],
      consumerStatuses: Object.fromEntries(
        PARAM_TRANSACTION_CONSUMERS.map((consumer) => [
          consumer,
          {
            consumer,
            ok: null,
            message: 'pending',
            state: 'pending',
            ts: now,
            traceId: event.traceId,
          },
        ]),
      ),
      deadlineTs: new Date(Date.now() + 3000).toISOString(),
      startedAt: now,
      completedAt: null,
      state: 'pending',
    };
    this.emitSnapshot();

    window.setTimeout(() => {
      const doneAt = new Date().toISOString();
      if (!this.state.lastTransaction || this.state.lastTransaction.transactionId !== transactionId) return;
      this.state.committedParams = deepCloneParams(nextParams);
      this.state.committedProfileName = nextProfileName;
      this.state.committedRuntimeParamVersion = nextVersion;
      this.state.lastTransaction = {
        ...this.state.lastTransaction,
        consumerStatuses: Object.fromEntries(
          PARAM_TRANSACTION_CONSUMERS.map((consumer) => [
            consumer,
            {
              consumer,
              ok: true,
              message: `${consumer} runtime parameters applied`,
              state: 'applied',
              ts: doneAt,
              traceId: event.traceId,
            },
          ]),
        ),
        completedAt: doneAt,
        state: 'applied',
      };
      this.state.lastParamApplyResult = {
        ok: true,
        message: 'runtime parameter apply confirmed by all consumers',
        ts: doneAt,
        reason,
        traceId: event.traceId,
        transactionId,
        state: 'applied',
        rollbackPerformed: false,
      };
      this.emitSnapshot();
      this.handlers?.onMessage(
        createMockInboundEvent('command_ack', {
          commandId: event.eventId,
          status: 'ack',
          lifecycleStatus: 'applied',
          message: 'runtime parameter apply confirmed by all consumers',
          traceId: event.traceId,
        }),
      );
    }, 120);
  }

  private profileNameForParams(params: MockState['params']): string {
    for (const [name, profile] of Object.entries(PARAM_PRESETS)) {
      if (JSON.stringify(profile) === JSON.stringify(params)) {
        return name;
      }
    }
    return '自定义';
  }

  private emitTelemetry(): void {
    const moving = ['MANUAL', 'PATROL', 'TRACK'].includes(this.state.mode) && !this.state.safeStop && !this.state.estop;
    const now = new Date().toISOString();
    const linear = moving ? Number((0.09 + Math.random() * 0.12).toFixed(2)) : 0;
    const angular = moving ? Number((Math.random() * 0.6 - 0.3).toFixed(2)) : 0;

    this.state.battery = clamp(Number((this.state.battery - 0.05).toFixed(2)), 12, 100) as number;
    this.state.voltage = Number((11.2 + Math.random() * 0.45).toFixed(2));

    this.handlers?.onMessage(
      createMockInboundEvent('chassis_state', {
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

    this.handlers?.onMessage(
      createMockInboundEvent('power_state', {
        batteryPercent: this.state.battery,
        batteryVoltage: this.state.voltage,
        lowPowerWarning: this.state.battery <= this.state.params.lowPowerThreshold,
        charging: false,
        lastUpdateAt: now,
      }),
    );
    this.handlers?.onMessage(
      createMockInboundEvent('vision_target', {
        targetType: moving ? 'inspection-marker' : 'idle-view',
        targetOffsetX: Number((Math.random() * 0.8 - 0.4).toFixed(2)),
        targetOffsetY: Number((Math.random() * 0.4 - 0.2).toFixed(2)),
        detectTimestamp: now,
        trackingReady: true,
        frameDrops: Math.floor(Math.random() * 4),
        lastUpdateAt: now,
      }),
    );

    if (Math.random() > 0.72) {
      const command = ['开始巡检', '停止巡检', '进入待机', '左转', '右转'][Math.floor(Math.random() * 5)];
      this.handlers?.onMessage(
        createMockInboundEvent('voice_cmd', {
          lastVoiceCommand: command,
          voiceConfidence: Number((0.78 + Math.random() * 0.17).toFixed(2)),
          speaking: false,
          lastSpeakText: '系统状态正常',
          wakeStatus: 'triggered',
          lastUpdateAt: now,
        }),
      );
    }

    if (this.state.mode === 'PATROL') {
      this.state.progress = clamp(Number((this.state.progress + 0.1).toFixed(2)), 0, 1) as number;
      this.state.completedPoints = Math.min(4, Math.max(this.state.completedPoints, Math.round(this.state.progress * 4)));
      this.state.currentWaypoint = DEFAULT_WAYPOINTS[Math.min(3, this.state.completedPoints)]?.id ?? 'P4';
      this.handlers?.onMessage(
        createMockInboundEvent('task_event', {
          patrolStatus: this.state.progress >= 1 ? 'completed' : 'running',
          currentWaypoint: this.state.currentWaypoint,
          progress: this.state.progress,
          completedPoints: this.state.completedPoints,
          totalPoints: 4,
          trackEnabled: false,
          lastTaskEvent: now,
          waypoints: DEFAULT_WAYPOINTS.map((point, index) => ({
            ...point,
            status: index < this.state.completedPoints ? 'done' : point.id === this.state.currentWaypoint ? 'running' : 'pending',
          })),
        }),
      );
      if (this.state.progress >= 1) this.state.mode = 'IDLE';
    }
  }

  private applyCommand(event: BridgeOutboundEvent): void {
    const now = new Date().toISOString();
    const log = (message: string, domain: 'CONTROL' | 'SAFETY' | 'TASK' | 'PARAM' | 'VOICE' = 'CONTROL') => {
      this.handlers?.onMessage(
        createMockInboundEvent('system_log', {
          id: uuid('log'),
          timestamp: now,
          level: domain === 'SAFETY' ? 'ERROR' : 'INFO',
          domain,
          message,
        }),
      );
    };

    switch (event.type) {
      case 'set_mode':
        this.state.mode = event.payload.mode;
        this.handlers?.onMessage(createMockInboundEvent('mode_state', { mode: event.payload.mode, isManualOverride: event.payload.mode === 'MANUAL', lastUpdateAt: now }));
        log(`模式切换为 ${event.payload.mode}`);
        break;
      case 'teleop_cmd':
        this.state.mode = 'MANUAL';
        this.handlers?.onMessage(createMockInboundEvent('chassis_state', { mode: 'MANUAL', isManualOverride: true, linearVelocity: event.payload.linear, angularVelocity: event.payload.angular, leftWheelSpeed: Number((event.payload.linear - event.payload.angular * 0.15).toFixed(2)), rightWheelSpeed: Number((event.payload.linear + event.payload.angular * 0.15).toFixed(2)), commandSource: 'ui', lastUpdateAt: now }));
        break;
      case 'stop_now':
        this.handlers?.onMessage(createMockInboundEvent('chassis_state', { linearVelocity: 0, angularVelocity: 0, leftWheelSpeed: 0, rightWheelSpeed: 0, lastUpdateAt: now }));
        log('已执行立即停车命令');
        break;
      case 'estop':
        this.state.estop = true;
        this.state.safeStop = true;
        this.state.mode = 'SAFE_STOP';
        this.handlers?.onMessage(createMockInboundEvent('fault_event', { level: 'critical', code: 'ESTOP', message: '前端触发急停', estopActive: true, safeStopActive: true, timeoutStopActive: false, lastUpdateAt: now }));
        this.handlers?.onMessage(createMockInboundEvent('mode_state', { mode: 'SAFE_STOP', lastUpdateAt: now }));
        log('急停已触发', 'SAFETY');
        break;
      case 'resume_from_safe_stop':
        this.state.estop = false;
        this.state.safeStop = false;
        this.state.faultLock = false;
        this.state.mode = 'IDLE';
        this.handlers?.onMessage(createMockInboundEvent('fault_event', { level: 'info', code: null, message: '安全停车已解除', estopActive: false, safeStopActive: false, timeoutStopActive: false, lastUpdateAt: now }));
        this.handlers?.onMessage(createMockInboundEvent('mode_state', { mode: 'IDLE', lastUpdateAt: now }));
        log('已从 SAFE_STOP 恢复到 IDLE', 'SAFETY');
        break;
      case 'start_patrol':
        this.state.mode = 'PATROL';
        this.state.progress = 0.25;
        this.state.completedPoints = 1;
        this.state.currentWaypoint = 'P2';
        this.handlers?.onMessage(createMockInboundEvent('task_event', { patrolStatus: 'running', currentWaypoint: 'P2', progress: 0.25, completedPoints: 1, totalPoints: 4, lastTaskEvent: now, waypoints: DEFAULT_WAYPOINTS.map((point, index) => ({ ...point, status: index === 0 ? 'done' : index === 1 ? 'running' : 'pending' })) }));
        this.handlers?.onMessage(createMockInboundEvent('mode_state', { mode: 'PATROL', lastUpdateAt: now }));
        log('巡检任务已开始', 'TASK');
        break;
      case 'pause_patrol':
        this.handlers?.onMessage(createMockInboundEvent('task_event', { patrolStatus: 'paused', lastTaskEvent: now }));
        log('巡检任务已暂停', 'TASK');
        break;
      case 'stop_patrol':
        this.state.mode = 'IDLE';
        this.state.progress = 0;
        this.state.completedPoints = 0;
        this.state.currentWaypoint = null;
        this.handlers?.onMessage(createMockInboundEvent('task_event', { patrolStatus: 'aborted', currentWaypoint: null, progress: 0, completedPoints: 0, totalPoints: 4, lastTaskEvent: now, waypoints: DEFAULT_WAYPOINTS }));
        this.handlers?.onMessage(createMockInboundEvent('mode_state', { mode: 'IDLE', lastUpdateAt: now }));
        log('巡检任务已停止', 'TASK');
        break;
      case 'apply_param_draft': {
        const nextParams = deepCloneParams({ ...this.state.params, ...event.payload.params });
        const nextProfileName = this.profileNameForParams(nextParams);
        this.beginParamTransaction(event, nextParams, nextProfileName, 'apply_param_draft');
        log(`已提交参数草稿事务 (${Object.keys(event.payload.params).length} 项)`, 'PARAM');
        break;
      }
      case 'apply_param_profile': {
        const profile = PARAM_PRESETS[event.payload.profileName];
        if (!profile) {
          this.handlers?.onMessage(createMockInboundEvent('command_ack', { commandId: event.eventId, status: 'rejected', lifecycleStatus: 'rejected', message: `未知参数配置：${event.payload.profileName}`, traceId: event.traceId }));
          log(`参数配置不存在：${event.payload.profileName}`, 'PARAM');
          break;
        }
        this.beginParamTransaction(event, deepCloneParams(profile), event.payload.profileName, `apply_param_profile:${event.payload.profileName}`);
        log(`已请求应用参数配置 ${event.payload.profileName}`, 'PARAM');
        break;
      }
      case 'speak_fixed_text':
        this.handlers?.onMessage(createMockInboundEvent('voice_cmd', { speaking: true, lastSpeakText: event.payload.text, lastVoiceCommand: '手动播报', voiceConfidence: 1, lastUpdateAt: now }));
        window.setTimeout(() => {
          this.handlers?.onMessage(createMockInboundEvent('voice_cmd', { speaking: false, lastSpeakText: event.payload.text, lastUpdateAt: new Date().toISOString() }));
        }, 900);
        log(`播报文本：${event.payload.text}`, 'VOICE');
        break;
      default:
        break;
    }
  }
}
