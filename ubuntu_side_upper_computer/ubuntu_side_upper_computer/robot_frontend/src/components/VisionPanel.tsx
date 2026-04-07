import { KeyValueGrid } from '@/components/KeyValueGrid';
import { SectionCard } from '@/components/SectionCard';
import { formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function VisionPanel() {
  const vision = useRobotStore((state) => state.vision);

  return (
    <SectionCard title="视觉结果">
      <KeyValueGrid
        items={[
          { label: '目标类型', value: vision.targetType ?? '--' },
          { label: '偏差 X', value: vision.targetOffsetX.toFixed(2) },
          { label: '偏差 Y', value: vision.targetOffsetY.toFixed(2) },
          { label: '二维码', value: vision.qrcodeText ?? '--', emphasis: Boolean(vision.qrcodeText) },
          { label: '丢帧计数', value: String(vision.frameDrops), emphasis: vision.frameDrops > 0 },
          { label: 'Tracking 就绪', value: vision.trackingReady ? '是' : '否' },
          { label: '最后检测', value: formatTimestamp(vision.detectTimestamp) }
        ]}
      />
      <div className="history-list">
        <span className="section-meta-title">二维码历史</span>
        {vision.qrcodeHistory.length === 0 ? <p className="muted">暂无二维码事件。</p> : null}
        {vision.qrcodeHistory.map((item) => (
          <div className="history-list-item" key={item.id}>
            <strong>{item.label}</strong>
            <span>{formatTimestamp(item.ts)}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
