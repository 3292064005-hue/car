import { expect, test, type Page } from '@playwright/test';

type MockBridgeOptions = {
  commandAck?: boolean;
};

async function installMockBridge(page: Page, options: MockBridgeOptions = {}): Promise<void> {
  const { commandAck = false } = options;
  await page.addInitScript(({ commandAckEnabled }) => {
    const now = () => new Date().toISOString();
    const createEvent = (type: string, payload: Record<string, unknown>) => ({
      eventId: `evt-${Math.random().toString(36).slice(2, 10)}`,
      type,
      ts: now(),
      source: 'bridge',
      sessionId: 'playwright-session',
      seq: 1,
      payload,
      protocolVersion: '4.0.0',
      schemaVersion: 'v4',
      origin: 'playwright-mock-bridge',
      compatibilityMode: 'native-v4'
    });

    const snapshotPayload = {
      connection: {
        rosConnected: true,
        bridgeConnected: true,
        stm32Connected: true,
        videoConnected: true,
        voiceConnected: true,
        reconnecting: false,
        latencyMs: 18,
        heartbeatAgeMs: 0,
        lastHeartbeatAt: now(),
        transportLabel: 'playwright-websocket',
        transportType: 'websocket',
        reconnectAttempts: 0,
        staleMotion: false,
        stalePower: false,
        staleVision: false,
        staleVoice: false,
        inboundRateHz: 5,
        outboundRateHz: 2,
        protocolVersion: '4.0.0',
        schemaVersion: 'v4',
        capabilities: ['command-ack', 'transport-diagnostics'],
        lastSnapshotVersion: 'v4',
        lastTraceId: null,
        compatibilityMode: 'native-v4'
      },
      motion: { mode: 'IDLE', lastUpdateAt: now() },
      power: { batteryPercent: 82, batteryVoltage: 11.9, lowPowerWarning: false, charging: false, lastUpdateAt: now() },
      vision: { targetType: 'marker', detectTimestamp: now(), trackingReady: true },
      voice: { wakeStatus: 'idle', recentCommands: [] },
      task: { totalPoints: 4, completedPoints: 0, progress: 0, patrolStatus: 'idle', waypoints: [] },
      fault: { level: 'info', code: null, message: null, safeStopActive: false, estopActive: false, timeoutStopActive: false, lastUpdateAt: now() },
      params: {
        maxLinearSpeed: 0.45,
        maxAngularSpeed: 1.1,
        teleopStep: 0.08,
        trackOffsetDeadband: 0.1,
        lowPowerThreshold: 25,
        reconnectTimeoutMs: 1500
      },
      logs: []
    };

    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      readonly url: string;
      readyState = MockWebSocket.CONNECTING;
      onopen: ((event?: unknown) => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;

      constructor(url: string) {
        this.url = url;
        window.setTimeout(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.({});
          this.onmessage?.({ data: JSON.stringify(createEvent('snapshot', snapshotPayload)) });
          this.onmessage?.({ data: JSON.stringify(createEvent('heartbeat', { bridgeConnected: true, rosConnected: true, stm32Connected: true, videoConnected: true, voiceConnected: true, latencyMs: 18 })) });
        }, 0);
      }

      send(raw: string): void {
        const command = JSON.parse(raw) as { eventId?: string; type?: string; payload?: { mode?: string } };
        if (commandAckEnabled && command.eventId) {
          window.setTimeout(() => {
            this.onmessage?.({
              data: JSON.stringify(
                createEvent('command_ack', {
                  commandId: command.eventId,
                  status: 'ack',
                  message: `已受理 ${command.type ?? 'unknown'}`
                }),
              ),
            });
            if (command.type === 'set_mode' && command.payload?.mode) {
              this.onmessage?.({
                data: JSON.stringify(
                  createEvent('mode_state', {
                    mode: command.payload.mode,
                    lastUpdateAt: now(),
                    isManualOverride: command.payload.mode === 'MANUAL'
                  }),
                ),
              });
            }
          }, 20);
        }
      }

      close(): void {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.();
      }
    }

    Object.defineProperty(window, 'WebSocket', {
      configurable: true,
      writable: true,
      value: MockWebSocket,
    });
  }, { commandAckEnabled: commandAck });
}

test('dashboard renders core panels', async ({ page }) => {
  await installMockBridge(page);
  await page.goto('/');
  await expect(page.getByText('巡检机器人控制台')).toBeVisible();
  await expect(page.getByText('连接状态')).toBeVisible();
  await expect(page.getByText('模式状态')).toBeVisible();
  await expect(page.getByText('视频主视图')).toBeVisible();
});

test('inspector page renders scenario buttons', async ({ page }) => {
  await installMockBridge(page);
  await page.goto('/inspector');
  await expect(page.getByText('Bridge 检查器')).toBeVisible();
  await expect(page.getByText('低压告警')).toBeVisible();
  await expect(page.getByText('ACK 超时')).toBeVisible();
});

test('replay page renders import controls', async ({ page }) => {
  await installMockBridge(page);
  await page.goto('/replay');
  await expect(page.getByText('会话回放')).toBeVisible();
  await expect(page.getByText('导入会话')).toBeVisible();
});

test('dashboard renders connection transport metadata', async ({ page }) => {
  await installMockBridge(page);
  await page.goto('/');
  await expect(page.getByText('传输类型')).toBeVisible();
  await expect(page.getByText('playwright-websocket')).toBeVisible();
});

test('websocket bridge path acknowledges a mode command', async ({ page }) => {
  await installMockBridge(page, { commandAck: true });
  await page.goto('/');
  await page.getByRole('button', { name: 'MANUAL' }).click();
  await expect(page.getByText('命令队列')).toBeVisible();
  await expect(page.getByText('set_mode')).toBeVisible();
  await expect(page.getByText('ack')).toBeVisible();
  await expect(page.getByText('已受理 set_mode')).toBeVisible();
});
