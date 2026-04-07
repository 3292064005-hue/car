import { robotBridge } from '@/bridge/client';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatDateTime } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function FaultPanel() {
  const fault = useRobotStore((state) => state.fault);
  const runtime = useRobotStore((state) => state.runtime);
  const ui = useRobotStore((state) => state.ui);

  const tone = fault.level === 'critical' ? 'danger' : fault.level === 'warning' ? 'warning' : 'neutral';

  return (
    <SectionCard title="故障与保护" right={<StatusPill label={fault.level.toUpperCase()} tone={tone} />}>
      <div className="fault-box">
        <p><strong>故障码：</strong>{fault.code ?? '--'}</p>
        <p><strong>描述：</strong>{fault.message ?? '当前无故障。'}</p>
        <p><strong>SAFE_STOP：</strong>{fault.safeStopActive ? '已触发' : '未触发'}</p>
        <p><strong>急停：</strong>{fault.estopActive ? '已触发' : '未触发'}</p>
        <p><strong>超时停车：</strong>{fault.timeoutStopActive ? '已触发' : '未触发'}</p>
        <p><strong>安全相位：</strong>{runtime.safetyPhase}</p>
        <p><strong>最近更新：</strong>{formatDateTime(fault.lastUpdateAt)}</p>
      </div>
      <div className="fault-checklist">
        <div>1. 确认底盘速度归零</div>
        <div>2. 检查 bridge 心跳与 stale 标志</div>
        <div>3. 检查电压是否恢复到阈值以上</div>
        <div>4. 人工确认后再恢复</div>
        {runtime.lastRejectedReason ? <div className="danger-text">最近拦截：{runtime.lastRejectedReason}</div> : null}
      </div>
      <div className="inline-actions">
        <button className="danger-btn" disabled={ui.demoReadonly} onClick={() => robotBridge.send('estop', { source: 'frontend' }, '触发急停')}>
          急停
        </button>
        <button className="primary-btn" disabled={ui.demoReadonly} onClick={() => robotBridge.send('resume_from_safe_stop', { source: 'frontend' }, '从 SAFE_STOP 恢复')}>
          从 SAFE_STOP 恢复
        </button>
      </div>
    </SectionCard>
  );
}
