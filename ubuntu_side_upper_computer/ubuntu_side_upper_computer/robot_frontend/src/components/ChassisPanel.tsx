import { KeyValueGrid } from '@/components/KeyValueGrid';
import { SectionCard } from '@/components/SectionCard';
import { HistoryStrip } from '@/components/HistoryStrip';
import { formatNumber, formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function ChassisPanel() {
  const motion = useRobotStore((state) => state.motion);
  const connection = useRobotStore((state) => state.connection);
  const history = useRobotStore((state) => state.history);

  return (
    <SectionCard title="底盘状态">
      <KeyValueGrid
        items={[
          { label: '线速度', value: `${formatNumber(motion.linearVelocity)} m/s` },
          { label: '角速度', value: `${formatNumber(motion.angularVelocity)} rad/s` },
          { label: '左轮速', value: `${formatNumber(motion.leftWheelSpeed)} m/s` },
          { label: '右轮速', value: `${formatNumber(motion.rightWheelSpeed)} m/s` },
          { label: '里程 X', value: `${formatNumber(motion.odomX)} m` },
          { label: '里程 Y', value: `${formatNumber(motion.odomY)} m` },
          { label: 'Yaw', value: `${formatNumber(motion.odomYaw)} rad` },
          { label: '控制来源', value: motion.commandSource, emphasis: motion.commandSource !== 'unknown' },
          { label: '人工接管', value: motion.isManualOverride ? '是' : '否', emphasis: motion.isManualOverride },
          { label: '更新时间', value: formatTimestamp(motion.lastUpdateAt), emphasis: connection.staleMotion }
        ]}
      />
      <div className="history-grid">
        <div>
          <span className="section-meta-title">左轮历史</span>
          <HistoryStrip values={history.leftWheel} suffix="m/s" />
        </div>
        <div>
          <span className="section-meta-title">右轮历史</span>
          <HistoryStrip values={history.rightWheel} suffix="m/s" />
        </div>
      </div>
    </SectionCard>
  );
}
