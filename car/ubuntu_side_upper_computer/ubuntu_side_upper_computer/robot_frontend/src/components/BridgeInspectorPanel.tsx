import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Download } from 'lucide-react';
import { MOCK_SCENARIOS } from '@/shared/constants';
import { downloadText, safeClipboardWrite, toJson } from '@/shared/utils';
import { SectionCard } from '@/components/SectionCard';
import { robotBridge } from '@/bridge/client';
import { useRobotStore } from '@/store/useRobotStore';

export function BridgeInspectorPanel() {
  const inspector = useRobotStore((state) => state.inspector);
  const connection = useRobotStore((state) => state.connection);
  const parentRef = useRef<HTMLDivElement | null>(null);
  const [filter, setFilter] = useState<'ALL' | 'in' | 'out' | 'rejected'>('ALL');
  const rows = useMemo(
    () => (filter === 'ALL' ? inspector.trace : inspector.trace.filter((item) => item.direction === filter)),
    [filter, inspector.trace]
  );

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 88,
    overscan: 8
  });

  const accepted = inspector.trace.filter((item) => item.verdict === 'accepted').length;
  const rejected = inspector.trace.filter((item) => item.verdict === 'rejected').length;
  const sent = inspector.trace.filter((item) => item.verdict === 'sent').length;

  return (
    <SectionCard
      title="Bridge 检查器"
      right={
        <div className="toolbar-inline">
          <select className="input-small" value={filter} onChange={(event) => setFilter(event.target.value as 'ALL' | 'in' | 'out' | 'rejected')}>
            <option value="ALL">全部</option>
            <option value="in">入站</option>
            <option value="out">出站</option>
            <option value="rejected">拒收</option>
          </select>
          <button className="ghost-btn small-btn" onClick={() => downloadText('bridge-trace.json', toJson(rows), 'application/json;charset=utf-8')}>
            <Download size={14} />导出 trace
          </button>
        </div>
      }
    >
      <div className="kv-grid">
        <div className="kv-item"><span>inbound 速率</span><strong>{connection.inboundRateHz} Hz</strong></div>
        <div className="kv-item"><span>outbound 速率</span><strong>{connection.outboundRateHz} Hz</strong></div>
        <div className="kv-item"><span>已接受</span><strong>{accepted}</strong></div>
        <div className="kv-item"><span>已拒收</span><strong>{rejected}</strong></div>
        <div className="kv-item"><span>已发送</span><strong>{sent}</strong></div>
        <div className="kv-item"><span>最后 traceId</span><strong>{connection.lastTraceId ?? '--'}</strong></div>
      </div>
      <div className="diff-box compact-box">
        <strong>协议与兼容层</strong>
        <div className="history-list-item"><span>{connection.protocolVersion}</span><span>{connection.schemaVersion}</span><span>{connection.compatibilityMode}</span></div>
        <div className="tag-row">
          {connection.capabilities.map((cap) => (
            <span key={cap} className="tag-chip">{cap}</span>
          ))}
        </div>
      </div>
      <div className="inline-actions wrap-start">
        {MOCK_SCENARIOS.map((scenario) => (
          <button key={scenario.id} className="ghost-btn small-btn" onClick={() => robotBridge.runLocalScenario(scenario.id)}>
            {scenario.label}
          </button>
        ))}
      </div>
      <div ref={parentRef} className="virtual-list inspector-list">
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const item = rows[virtualRow.index];
            return (
              <div
                key={item.id}
                className={`trace-item trace-${item.direction}`}
                style={{ position: 'absolute', top: 0, left: 0, width: '100%', transform: `translateY(${virtualRow.start}px)` }}
              >
                <div className="log-head">
                  <strong>{item.type}</strong>
                  <span>{item.direction.toUpperCase()}</span>
                  <span>{item.verdict}</span>
                  <span>{item.timestamp}</span>
                </div>
                {item.note ? <p>{item.note}</p> : null}
                <pre>{item.raw}</pre>
                <div className="toolbar-inline">
                  <button className="ghost-btn small-btn" onClick={() => safeClipboardWrite(item.raw)}>复制原始记录</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SectionCard>
  );
}
