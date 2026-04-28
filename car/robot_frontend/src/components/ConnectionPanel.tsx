import { KeyValueGrid } from '@/components/KeyValueGrid';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatDateTime } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function ConnectionPanel() {
  const connection = useRobotStore((state) => state.connection);

  const tone = (value: boolean): 'success' | 'danger' => (value ? 'success' : 'danger');

  return (
    <SectionCard title="连接状态">
      <div className="pill-row">
        <StatusPill label={`ROS2 ${connection.rosConnected ? '在线' : '离线'}`} tone={tone(connection.rosConnected)} />
        <StatusPill label={`Bridge ${connection.bridgeConnected ? '在线' : '离线'}`} tone={tone(connection.bridgeConnected)} />
        <StatusPill label={`STM32 ${connection.stm32Connected ? '在线' : '离线'}`} tone={tone(connection.stm32Connected)} />
        <StatusPill label={`视频 ${connection.videoConnected ? '正常' : '断流'}`} tone={tone(connection.videoConnected)} />
        <StatusPill label={`语音 ${connection.voiceConnected ? '正常' : '异常'}`} tone={tone(connection.voiceConnected)} />
      </div>
      <KeyValueGrid
        items={[
          { label: '传输类型', value: connection.transportType },
          { label: 'bridge 标签', value: connection.transportLabel },
          { label: '延迟', value: `${connection.latencyMs} ms`, emphasis: connection.latencyMs > 120 },
          { label: '心跳年龄', value: `${connection.heartbeatAgeMs} ms`, emphasis: connection.heartbeatAgeMs > 900 },
          { label: '最近心跳', value: formatDateTime(connection.lastHeartbeatAt) },
          { label: '重连状态', value: connection.reconnecting ? `重连中 (${connection.reconnectAttempts})` : '稳定' },
          { label: 'inbound', value: `${connection.inboundRateHz} Hz`, emphasis: connection.inboundRateHz === 0 },
          { label: 'outbound', value: `${connection.outboundRateHz} Hz`, emphasis: connection.outboundRateHz === 0 },
          { label: 'Wi‑Fi transport', value: connection.wifiTransportReady ? 'ready' : 'not ready', emphasis: connection.wifiTransportReady === false },
          { label: 'UART board', value: connection.uartBoardReady ? 'ready' : 'not ready', emphasis: connection.uartBoardReady === false },
          { label: 'motion heartbeat', value: connection.motionHeartbeatReady ? 'ready' : 'not ready', emphasis: connection.motionHeartbeatReady === false },
          { label: 'command link', value: connection.commandLinkReady ? 'ready' : 'not ready', emphasis: connection.commandLinkReady === false },
          { label: 'gateway ready', value: connection.gatewayReady ? 'ready' : 'not ready', emphasis: connection.gatewayReady === false },
          { label: 'operator surface', value: connection.operatorSurfaceReady ? 'ready' : 'not ready', emphasis: connection.operatorSurfaceReady === false },
          { label: '接入面', value: connection.websocketSurfaceKind ?? 'unknown', emphasis: connection.websocketSurfaceKind !== 'api_facade' },
          { label: '接入权限模型', value: connection.websocketSurfaceAuthority ?? 'unknown', emphasis: connection.websocketSurfaceAuthority !== 'authoritative_operator' },
          { label: '接入告警', value: connection.websocketSurfaceMismatch ? (connection.websocketSurfaceMismatchReason ?? 'surface_mismatch') : 'none', emphasis: connection.websocketSurfaceMismatch === true },
          { label: '会话角色', value: connection.sessionRole ?? 'unknown', emphasis: connection.sessionWriteEnabled === false },
          { label: '会话写权限', value: connection.sessionWriteEnabled === false ? '只读' : '可写', emphasis: connection.sessionWriteEnabled === false },
          { label: '会话说明', value: connection.sessionAccessReason ?? '未声明' },
          { label: 'motion stale', value: connection.staleMotion ? '是' : '否', emphasis: connection.staleMotion },
          { label: 'vision stale', value: connection.staleVision ? '是' : '否', emphasis: connection.staleVision }
        ]}
      />
    </SectionCard>
  );
}
