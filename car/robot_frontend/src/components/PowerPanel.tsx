import { HistoryStrip } from '@/components/HistoryStrip';
import { KeyValueGrid } from '@/components/KeyValueGrid';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function PowerPanel() {
  const power = useRobotStore((state) => state.power);
  const history = useRobotStore((state) => state.history);
  const connection = useRobotStore((state) => state.connection);

  return (
    <SectionCard
      title="电源状态"
      right={<StatusPill label={power.lowPowerWarning ? '低压告警' : '电量正常'} tone={power.lowPowerWarning ? 'warning' : 'success'} />}
    >
      <KeyValueGrid
        items={[
          { label: '电量', value: `${power.batteryPercent.toFixed(1)} %`, emphasis: power.batteryPercent <= 25 },
          { label: '电压', value: `${power.batteryVoltage.toFixed(2)} V`, emphasis: power.batteryVoltage < 11.3 },
          { label: '充电状态', value: power.charging ? '充电中' : '放电中' },
          { label: '风险等级', value: power.lowPowerWarning ? '需降级' : '正常' },
          { label: '最新更新', value: formatTimestamp(power.lastUpdateAt), emphasis: connection.stalePower }
        ]}
      />
      <div>
        <span className="section-meta-title">电量历史</span>
        <HistoryStrip values={history.battery} suffix="%" />
      </div>
    </SectionCard>
  );
}
