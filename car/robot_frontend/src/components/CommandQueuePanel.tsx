import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function CommandQueuePanel() {
  const commands = useRobotStore((state) => state.commands);

  const phaseLabel = (phase: string) => {
    const labels: Record<string, string> = {
      client_sent: '前端已发送',
      api_accepted: 'API 已接收',
      bridge_queued: 'Bridge 已排队',
      handler_dispatched: 'Handler 已分发',
      ros_accepted: 'ROS 已接收',
      business_completed: '业务已完成',
      failed: '失败终态',
      timed_out: '超时终态',
    };
    return labels[phase] ?? phase;
  };

  const tone = (status: string) => {
    if (status === 'ack' || status === 'accepted' || status === 'applied' || status === 'completed') return 'success' as const;
    if (status === 'queued' || status === 'sent') return 'warning' as const;
    return 'danger' as const;
  };

  return (
    <SectionCard title="命令队列" compact>
      <div className="command-list">
        {commands.length === 0 ? <p className="muted">暂无命令记录。</p> : null}
        {commands.slice(0, 10).map((command) => (
          <div className="command-item" key={command.id}>
            <div className="command-head">
              <strong>{command.type}</strong>
              <StatusPill label={`${command.status} · ${phaseLabel(command.lifecyclePhase)}`} tone={tone(command.status)} />
            </div>
            <p>{command.summary}</p>
            <small className="muted">
              创建 {formatTimestamp(command.createdAt)} · 更新 {formatTimestamp(command.updatedAt)} · 优先级 {command.priority}
              {command.ackLatencyMs !== undefined ? ` · ACK ${command.ackLatencyMs}ms` : ''} · 阶段 {phaseLabel(command.lifecyclePhase)}
            </small>
            {command.dangerous ? <small className="accent">危险命令：已纳入审计。</small> : null}
            {command.error ? <small className="danger-text">{command.error}</small> : null}
            {command.lifecycleHistory.length > 0 ? (
              <small className="muted">最近阶段：{command.lifecycleHistory.slice(0, 3).map((item) => `${phaseLabel(item.phase)}:${item.status}`).join(' / ')}</small>
            ) : null}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
