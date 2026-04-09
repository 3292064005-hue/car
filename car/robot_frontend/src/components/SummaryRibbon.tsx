import { BatteryMedium, Gauge, ShieldAlert, Wifi } from 'lucide-react';
import { SectionCard } from '@/components/SectionCard';
import { useRobotStore } from '@/store/useRobotStore';

export function SummaryRibbon() {
  const connection = useRobotStore((state) => state.connection);
  const power = useRobotStore((state) => state.power);
  const runtime = useRobotStore((state) => state.runtime);
  const motion = useRobotStore((state) => state.motion);

  const items = [
    { icon: Wifi, label: '链路延迟', value: `${connection.latencyMs} ms` },
    { icon: Gauge, label: '当前模式', value: motion.mode },
    { icon: BatteryMedium, label: '电量', value: `${power.batteryPercent.toFixed(1)} %` },
    { icon: ShieldAlert, label: '保护状态', value: runtime.safetyPhase }
  ];

  return (
    <SectionCard title="运行摘要" compact>
      <div className="summary-ribbon">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div className="summary-tile" key={item.label}>
              <div className="summary-icon"><Icon size={18} /></div>
              <div>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
