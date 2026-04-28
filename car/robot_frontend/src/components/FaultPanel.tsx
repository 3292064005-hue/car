import { robotBridge } from '@/bridge/client';
import { commandButtonState } from '@/bridge/commandPolicy';
import { FeatureMaturityPills } from '@/components/FeatureMaturityPills';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatDateTime } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function FaultPanel() {
  const fault = useRobotStore((state) => state.fault);
  const runtime = useRobotStore((state) => state.runtime);
  const ui = useRobotStore((state) => state.ui);

  const tone = fault.level === 'critical' ? 'danger' : fault.level === 'warning' ? 'warning' : 'neutral';
  const estopState = commandButtonState('estop', { source: 'frontend' });
  const resumeState = commandButtonState('resume_from_safe_stop', { source: 'frontend' });
  const resetFaultState = commandButtonState('reset_fault', { source: 'frontend' });
  const saveSnapshotState = commandButtonState('save_snapshot', { source: 'frontend' });

  return (
    <SectionCard title="故障与保护" right={<div className="toolbar-inline"><FeatureMaturityPills featureIds={['operator.safety_recovery', 'operator.snapshot_capture']} /><StatusPill label={fault.level.toUpperCase()} tone={tone} /></div>}>
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
      <div className="inline-actions wrap-start">
        <button className="danger-btn" title={estopState.reason} disabled={ui.demoReadonly || estopState.disabled} onClick={() => robotBridge.send('estop', { source: 'frontend' }, '触发急停')}>
          急停
        </button>
        <button className="primary-btn" title={resumeState.reason} disabled={ui.demoReadonly || resumeState.disabled} onClick={() => robotBridge.send('resume_from_safe_stop', { source: 'frontend' }, '从 SAFE_STOP 恢复')}>
          从 SAFE_STOP 恢复
        </button>
        <button
          className="ghost-btn"
          disabled={ui.demoReadonly || resetFaultState.disabled}
          title={ui.demoReadonly ? '当前启用了本地演示锁。' : resetFaultState.reason}
          onClick={() => robotBridge.send('reset_fault', { source: 'frontend' }, '执行故障复位')}
        >
          故障复位
        </button>
        <button
          className="ghost-btn"
          disabled={ui.demoReadonly || saveSnapshotState.disabled}
          title={ui.demoReadonly ? '当前启用了本地演示锁。' : saveSnapshotState.reason}
          onClick={() => robotBridge.send('save_snapshot', { source: 'frontend' }, '保存视觉快照')}
        >
          保存快照
        </button>
      </div>
    </SectionCard>
  );
}
