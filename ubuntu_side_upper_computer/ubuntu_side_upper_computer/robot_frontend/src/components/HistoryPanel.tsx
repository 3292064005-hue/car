import { SectionCard } from '@/components/SectionCard';
import { HistoryStrip } from '@/components/HistoryStrip';
import { useRobotStore } from '@/store/useRobotStore';

export function HistoryPanel() {
  const history = useRobotStore((state) => state.history);

  return (
    <SectionCard title="趋势样本">
      <div className="history-grid">
        <div>
          <span className="section-meta-title">链路延迟</span>
          <HistoryStrip values={history.latency} suffix=" ms" />
        </div>
        <div>
          <span className="section-meta-title">ACK 延迟</span>
          <HistoryStrip values={history.ackLatency} suffix=" ms" />
        </div>
        <div>
          <span className="section-meta-title">电量</span>
          <HistoryStrip values={history.battery} suffix=" %" />
        </div>
        <div>
          <span className="section-meta-title">丢帧</span>
          <HistoryStrip values={history.frameDrops} suffix=" 帧" />
        </div>
      </div>
    </SectionCard>
  );
}
