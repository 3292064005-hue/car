import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Download, Upload } from 'lucide-react';
import { SectionCard } from '@/components/SectionCard';
import { average, downloadText, formatDateTime, formatNumber, parseReplaySession, percentile, toJson } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function ReplayPanel() {
  const replay = useRobotStore((state) => state.replay);
  const loadReplaySession = useRobotStore((state) => state.loadReplaySession);
  const setReplayIndex = useRobotStore((state) => state.setReplayIndex);
  const clearReplaySession = useRobotStore((state) => state.clearReplaySession);
  const [error, setError] = useState<string | null>(null);
  const rows = useMemo(() => replay.session?.logs ?? [], [replay.session]);
  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 82,
    overscan: 8
  });

  const current = replay.session?.logs[replay.activeLogIndex] ?? null;
  const progress = rows.length ? replay.activeLogIndex / Math.max(1, rows.length - 1) : 0;
  const historyIndex = replay.session ? Math.floor(progress * Math.max(0, replay.session.history.latency.length - 1)) : 0;

  const onFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const parsed = parseReplaySession(text);
    if (!parsed) {
      setError('回放文件不是合法 JSON。');
      return;
    }
    setError(null);
    loadReplaySession({ ...parsed, sourceName: file.name });
  };

  return (
    <SectionCard
      title="离线会话回放"
      right={
        <div className="toolbar-inline">
          <label className="ghost-btn small-btn">
            <Upload size={14} />导入离线会话
            <input type="file" accept="application/json" hidden onChange={onFileChange} />
          </label>
          <button className="ghost-btn small-btn" disabled={!replay.session} onClick={() => replay.session && downloadText('offline-session-export.json', toJson(replay.session), 'application/json;charset=utf-8')}>
            <Download size={14} />导出离线副本
          </button>
          <button className="ghost-btn small-btn" disabled={!replay.session} onClick={clearReplaySession}>清空</button>
        </div>
      }
    >
      {error ? <div className="danger-text">{error}</div> : null}
      {!replay.session ? <p className="muted">导入前端导出的离线会话 JSON，即可在只读模式下查看日志、命令、趋势和检查器记录。该能力不依赖后端 session replay 服务。</p> : null}
      {replay.session ? (
        <>
          <div className="kv-grid">
            <div className="kv-item"><span>离线来源</span><strong>{replay.session.sourceName}</strong></div>
            <div className="kv-item"><span>离线导出时间</span><strong>{formatDateTime(replay.session.exportedAt)}</strong></div>
            <div className="kv-item"><span>日志总数</span><strong>{replay.session.logs.length}</strong></div>
            <div className="kv-item"><span>当前离线游标</span><strong>{replay.activeLogIndex + 1}</strong></div>
            <div className="kv-item"><span>ACK 平均</span><strong>{formatNumber(average(replay.session.history.ackLatency), 1)} ms</strong></div>
            <div className="kv-item"><span>ACK P95</span><strong>{formatNumber(percentile(replay.session.history.ackLatency, 95), 1)} ms</strong></div>
          </div>
          <div className="replay-slider-row">
            <input type="range" min={0} max={Math.max(0, rows.length - 1)} value={replay.activeLogIndex} onChange={(event) => setReplayIndex(Number(event.target.value))} />
            <span className="muted">{Math.round(progress * 100)}%</span>
          </div>
          <div className="kv-grid compact-grid">
            <div className="kv-item"><span>离线延迟样本</span><strong>{replay.session.history.latency[historyIndex] ?? 0} ms</strong></div>
            <div className="kv-item"><span>离线电量样本</span><strong>{replay.session.history.battery[historyIndex] ?? 0} %</strong></div>
            <div className="kv-item"><span>离线左轮样本</span><strong>{formatNumber(replay.session.history.leftWheel[historyIndex] ?? 0, 2)}</strong></div>
            <div className="kv-item"><span>离线右轮样本</span><strong>{formatNumber(replay.session.history.rightWheel[historyIndex] ?? 0, 2)}</strong></div>
          </div>
          <div ref={parentRef} className="virtual-list replay-list">
            <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const item = rows[virtualRow.index];
                return (
                  <button
                    key={item.id}
                    className={`replay-row ${virtualRow.index === replay.activeLogIndex ? 'active' : ''}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', transform: `translateY(${virtualRow.start}px)` }}
                    onClick={() => setReplayIndex(virtualRow.index)}
                  >
                    <div className="log-head">
                      <strong>{item.level}</strong>
                      <span>{item.domain}</span>
                      <span>{formatDateTime(item.timestamp)}</span>
                    </div>
                    <p>{item.message}</p>
                  </button>
                );
              })}
            </div>
          </div>
          {current ? (
            <div className="diff-box">
              <strong>当前日志详情</strong>
              <div className="history-list-item"><span>{current.domain}</span><span>{current.level}</span><span>{formatDateTime(current.timestamp)}</span></div>
              <p>{current.message}</p>
              {current.details ? <small className="muted">{current.details}</small> : null}
              {replay.session.commands?.length ? <small className="muted">关联命令总数：{replay.session.commands.length}</small> : null}
              {replay.session.inspectorTrace?.length ? <small className="muted">检查器记录：{replay.session.inspectorTrace.length}</small> : null}
            </div>
          ) : null}
        </>
      ) : null}
    </SectionCard>
  );
}
