import { useMemo, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Download } from 'lucide-react';
import { SectionCard } from '@/components/SectionCard';
import { LOG_DOMAINS } from '@/shared/constants';
import { downloadText, exportLogsAsCsv, formatDateTime } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function LogPanel() {
  const logs = useRobotStore((state) => state.logs);
  const ui = useRobotStore((state) => state.ui);
  const setUiFilter = useRobotStore((state) => state.setUiFilter);
  const snapshot = useRobotStore((state) => state.exportStateSnapshot);

  const filtered = useMemo(() => {
    return logs.filter((item) => {
      const keywordMatch = !ui.logKeyword || `${item.domain} ${item.message} ${item.details ?? ''}`.toLowerCase().includes(ui.logKeyword.toLowerCase());
      const levelMatch = ui.logLevel === 'ALL' || item.level === ui.logLevel;
      const domainMatch = ui.logDomain === 'ALL' || item.domain === ui.logDomain;
      return keywordMatch && levelMatch && domainMatch;
    });
  }, [logs, ui.logDomain, ui.logKeyword, ui.logLevel]);

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 84,
    overscan: 8
  });

  return (
    <SectionCard
      title="事件日志"
      right={
        <div className="toolbar-inline">
          <button className="ghost-btn small-btn" onClick={() => downloadText('robot-logs.csv', exportLogsAsCsv(filtered), 'text/csv;charset=utf-8')}>
            <Download size={14} />导出 CSV
          </button>
          <button className="ghost-btn small-btn" onClick={() => {
            const state = snapshot();
            downloadText('robot-session.json', state.json, 'application/json;charset=utf-8');
          }}>
            <Download size={14} />导出会话
          </button>
        </div>
      }
    >
      <div className="log-filters">
        <input className="input-small" placeholder="关键词" value={ui.logKeyword} onChange={(event) => setUiFilter({ logKeyword: event.target.value })} />
        <select className="input-small" value={ui.logLevel} onChange={(event) => setUiFilter({ logLevel: event.target.value as typeof ui.logLevel })}>
          <option value="ALL">全部级别</option>
          <option value="INFO">INFO</option>
          <option value="WARN">WARN</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <select className="input-small" value={ui.logDomain} onChange={(event) => setUiFilter({ logDomain: event.target.value as typeof ui.logDomain })}>
          {LOG_DOMAINS.map((domain) => (
            <option key={domain} value={domain}>{domain}</option>
          ))}
        </select>
      </div>
      <div ref={parentRef} className="virtual-list log-list-virtual">
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const log = filtered[virtualRow.index];
            return (
              <div className="log-item" key={log.id} style={{ position: 'absolute', top: 0, left: 0, width: '100%', transform: `translateY(${virtualRow.start}px)` }}>
                <div className="log-head">
                  <span>{formatDateTime(log.timestamp)}</span>
                  <strong>{log.level}</strong>
                  <span>{log.domain}</span>
                </div>
                <p>{log.message}</p>
                {log.details ? <small className="muted">{log.details}</small> : null}
              </div>
            );
          })}
        </div>
      </div>
    </SectionCard>
  );
}
