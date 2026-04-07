import { Download } from 'lucide-react';
import { SectionCard } from '@/components/SectionCard';
import { downloadText, exportCommandsAsCsv, exportLogsAsCsv, formatNumber, percentile, toJson, average } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function ReportSummaryPanel() {
  const logs = useRobotStore((state) => state.logs);
  const commands = useRobotStore((state) => state.commands);
  const history = useRobotStore((state) => state.history);
  const connection = useRobotStore((state) => state.connection);
  const runtime = useRobotStore((state) => state.runtime);
  const exportStateSnapshot = useRobotStore((state) => state.exportStateSnapshot);

  const acked = commands.filter((item) => item.status === 'ack' || item.status === 'applied' || item.status === 'completed');
  const rejected = commands.filter((item) => item.status === 'rejected' || item.status === 'timeout' || item.status === 'denied' || item.status === 'cancelled');
  const criticalLogs = logs.filter((item) => item.level === 'ERROR' || item.level === 'CRITICAL');
  const summary = {
    protocolVersion: connection.protocolVersion,
    schemaVersion: connection.schemaVersion,
    compatibilityMode: connection.compatibilityMode,
    safetyPhase: runtime.safetyPhase,
    taskPhase: runtime.taskPhase,
    ackAvg: average(history.ackLatency),
    ackP95: percentile(history.ackLatency, 95),
    batteryMin: history.battery.length ? Math.min(...history.battery) : 0,
    frameDropMax: history.frameDrops.length ? Math.max(...history.frameDrops) : 0,
    commandStats: {
      total: commands.length,
      acked: acked.length,
      rejected: rejected.length,
      superseded: commands.filter((item) => item.status === 'superseded').length
    },
    criticalLogs: criticalLogs.length
  };

  return (
    <SectionCard
      title="运行摘要"
      right={
        <div className="toolbar-inline">
          <button className="ghost-btn small-btn" onClick={() => downloadText('run-report.json', toJson(summary), 'application/json;charset=utf-8')}>
            <Download size={14} />摘要 JSON
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText('commands.csv', exportCommandsAsCsv(commands), 'text/csv;charset=utf-8')}>
            <Download size={14} />命令 CSV
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText('logs.csv', exportLogsAsCsv(logs), 'text/csv;charset=utf-8')}>
            <Download size={14} />日志 CSV
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText('session-export.json', exportStateSnapshot().json, 'application/json;charset=utf-8')}>
            <Download size={14} />会话 JSON
          </button>
        </div>
      }
    >
      <div className="kv-grid">
        <div className="kv-item"><span>协议版本</span><strong>{connection.protocolVersion}</strong></div>
        <div className="kv-item"><span>Schema 版本</span><strong>{connection.schemaVersion}</strong></div>
        <div className="kv-item"><span>兼容层</span><strong>{connection.compatibilityMode}</strong></div>
        <div className="kv-item"><span>安全相位</span><strong>{runtime.safetyPhase}</strong></div>
        <div className="kv-item"><span>任务相位</span><strong>{runtime.taskPhase}</strong></div>
        <div className="kv-item"><span>ACK 平均</span><strong>{formatNumber(summary.ackAvg, 1)} ms</strong></div>
        <div className="kv-item"><span>ACK P95</span><strong>{formatNumber(summary.ackP95, 1)} ms</strong></div>
        <div className="kv-item"><span>最低电量</span><strong>{formatNumber(summary.batteryMin, 1)} %</strong></div>
        <div className="kv-item"><span>最大丢帧</span><strong>{summary.frameDropMax}</strong></div>
        <div className="kv-item"><span>关键日志</span><strong>{criticalLogs.length}</strong></div>
        <div className="kv-item"><span>ACK 成功</span><strong>{acked.length}/{commands.length || 0}</strong></div>
        <div className="kv-item"><span>异常命令</span><strong>{rejected.length}</strong></div>
      </div>
      <div className="diff-box compact-box">
        <strong>bridge capabilities</strong>
        <div className="tag-row">
          {connection.capabilities.map((cap) => (
            <span key={cap} className="tag-chip">{cap}</span>
          ))}
        </div>
      </div>
    </SectionCard>
  );
}
