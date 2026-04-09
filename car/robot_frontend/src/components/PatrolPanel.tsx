import { robotBridge } from '@/bridge/client';
import { commandButtonState } from '@/bridge/commandPolicy';
import { SectionCard } from '@/components/SectionCard';
import { useRobotStore } from '@/store/useRobotStore';

export function PatrolPanel() {
  const task = useRobotStore((state) => state.task);
  const runtime = useRobotStore((state) => state.runtime);
  const ui = useRobotStore((state) => state.ui);
  const startPatrol = commandButtonState('start_patrol', { source: 'frontend' });
  const pausePatrol = commandButtonState('pause_patrol', { source: 'frontend' });
  const stopPatrol = commandButtonState('stop_patrol', { source: 'frontend' });

  return (
    <SectionCard title="巡检任务">
      <div className="patrol-summary">
        <div>
          <span>任务状态</span>
          <strong>{task.patrolStatus}</strong>
        </div>
        <div>
          <span>运行相位</span>
          <strong>{runtime.taskPhase}</strong>
        </div>
        <div>
          <span>当前点位</span>
          <strong>{task.currentWaypoint ?? '--'}</strong>
        </div>
        <div>
          <span>完成进度</span>
          <strong>{Math.round(task.progress * 100)}%</strong>
        </div>
        <div>
          <span>Action 相位</span>
          <strong>{task.actionPhase ?? '--'}</strong>
        </div>
        <div>
          <span>Action 消息</span>
          <strong>{task.actionMessage ?? '--'}</strong>
        </div>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, task.progress * 100))}%` }} />
      </div>
      <div className="inline-actions">
        <button className="primary-btn" title={startPatrol.reason} disabled={ui.demoReadonly || startPatrol.disabled} onClick={() => robotBridge.send('start_patrol', { source: 'frontend' }, '开始巡检任务')}>开始巡检</button>
        <button className="ghost-btn" title={pausePatrol.reason} disabled={ui.demoReadonly || pausePatrol.disabled} onClick={() => robotBridge.send('pause_patrol', { source: 'frontend' }, '暂停巡检任务')}>暂停巡检</button>
        <button className="danger-btn" title={stopPatrol.reason} disabled={ui.demoReadonly || stopPatrol.disabled} onClick={() => robotBridge.send('stop_patrol', { source: 'frontend' }, '停止巡检任务')}>停止巡检</button>
      </div>
      <div className="waypoint-list">
        {task.waypoints.map((point) => (
          <div key={point.id} className={`waypoint-item status-${point.status}`}>
            <strong>{point.label}</strong>
            <span>{point.status}</span>
            {point.note ? <small className="muted">{point.note}</small> : null}
          </div>
        ))}
      </div>
      <p className="muted">任务页现在保留了状态、相位、点位和失败备注，便于联调时定位中断原因。</p>
    </SectionCard>
  );
}
