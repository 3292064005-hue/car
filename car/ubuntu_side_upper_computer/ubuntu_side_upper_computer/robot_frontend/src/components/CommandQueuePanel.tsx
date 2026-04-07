import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function CommandQueuePanel() {
  const commands = useRobotStore((state) => state.commands);

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
              <StatusPill label={command.status} tone={tone(command.status)} />
            </div>
            <p>{command.summary}</p>
            <small className="muted">
              创建 {formatTimestamp(command.createdAt)} · 更新 {formatTimestamp(command.updatedAt)} · 优先级 {command.priority}
              {command.ackLatencyMs !== undefined ? ` · ACK ${command.ackLatencyMs}ms` : ''}
            </small>
            {command.dangerous ? <small className="accent">危险命令：已纳入审计。</small> : null}
            {command.error ? <small className="danger-text">{command.error}</small> : null}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
