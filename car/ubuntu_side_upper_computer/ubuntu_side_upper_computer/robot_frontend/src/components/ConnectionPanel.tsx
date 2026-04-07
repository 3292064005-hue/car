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
          { label: 'motion stale', value: connection.staleMotion ? '是' : '否', emphasis: connection.staleMotion },
          { label: 'vision stale', value: connection.staleVision ? '是' : '否', emphasis: connection.staleVision }
        ]}
      />
    </SectionCard>
  );
}
