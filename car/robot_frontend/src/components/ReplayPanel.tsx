import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Download, ShieldCheck, Upload } from 'lucide-react';
import { FeatureMaturityPills } from '@/components/FeatureMaturityPills';
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
    overscan: 8,
  });

  const current = replay.session?.logs[replay.activeLogIndex] ?? null;
  const progress = rows.length ? replay.activeLogIndex / Math.max(1, rows.length - 1) : 0;
  const historyIndex = replay.session ? Math.floor(progress * Math.max(0, replay.session.history.latency.length - 1)) : 0;
  const isSystemBundle = replay.session?.kind === 'system-replay-bundle';
  const systemSession = replay.session?.kind === 'system-replay-bundle' ? replay.session : null;

  const onFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const parsed = parseReplaySession(text);
    if (!parsed) {
      setError('回放文件不是受支持的浏览器离线回放或系统级证据包 JSON。');
      return;
    }
    setError(null);
    loadReplaySession({ ...parsed, sourceName: file.name });
  };

  const downloadName = isSystemBundle ? 'system-replay-bundle.json' : 'browser-session-replay.json';

  return (
    <SectionCard
      title={isSystemBundle ? '系统级回放证据包' : '浏览器离线回放'}
      right={
        <div className="toolbar-inline">
          <FeatureMaturityPills featureIds={['observability.system_replay_evidence']} />
          <label className="ghost-btn small-btn">
            <Upload size={14} />导入回放
            <input type="file" accept="application/json" hidden onChange={onFileChange} />
          </label>
          <button className="ghost-btn small-btn" disabled={!replay.session} onClick={() => replay.session && downloadText(downloadName, toJson(replay.session), 'application/json;charset=utf-8')}>
            <Download size={14} />导出当前副本
          </button>
          <button className="ghost-btn small-btn" disabled={!replay.session} onClick={clearReplaySession}>清空</button>
        </div>
      }
    >
      {error ? <div className="danger-text">{error}</div> : null}
      {!replay.session ? <p className="muted">导入浏览器离线回放 JSON 或系统级 replay 证据包，即可在只读模式下查看日志、命令、趋势与追踪关联。浏览器离线回放不等于系统级验收证据。</p> : null}
      {replay.session ? (
        <>
          <div className="kv-grid">
            <div className="kv-item"><span>来源</span><strong>{replay.session.sourceName}</strong></div>
            <div className="kv-item"><span>导出时间</span><strong>{formatDateTime(replay.session.exportedAt)}</strong></div>
            <div className="kv-item"><span>日志总数</span><strong>{replay.session.logs.length}</strong></div>
            <div className="kv-item"><span>当前游标</span><strong>{replay.activeLogIndex + 1}</strong></div>
            <div className="kv-item"><span>ACK 平均</span><strong>{formatNumber(average(replay.session.history.ackLatency), 1)} ms</strong></div>
            <div className="kv-item"><span>ACK P95</span><strong>{formatNumber(percentile(replay.session.history.ackLatency, 95), 1)} ms</strong></div>
          </div>
          <div className="kv-grid compact-grid">
            <div className="kv-item"><span>证据级别</span><strong>{isSystemBundle ? 'system-evidence' : 'browser-only'}</strong></div>
            <div className="kv-item"><span>命令数</span><strong>{replay.session.commands?.length ?? 0}</strong></div>
            <div className="kv-item"><span>检查器记录</span><strong>{replay.session.inspectorTrace?.length ?? 0}</strong></div>
            {isSystemBundle ? (
              <>
                <div className="kv-item"><span>Topic 样本</span><strong>{systemSession?.topics.length ?? 0}</strong></div>
                <div className="kv-item"><span>Service/Action 事件</span><strong>{systemSession?.serviceActionEvents.length ?? 0}</strong></div>
                <div className="kv-item"><span>Trace 关联</span><strong>{systemSession?.traceCorrelation.length ?? 0}</strong></div>
              </>
            ) : null}
          </div>
          {isSystemBundle ? (
            <div className="diff-box">
              <strong><ShieldCheck size={16} />系统级 evidence metadata</strong>
              <div className="history-list-item"><span>session</span><span>{systemSession?.sessionMetadata.sessionId ?? '-'}</span><span>{systemSession?.sessionMetadata.profileName ?? '-'}</span></div>
              <div className="history-list-item"><span>provider</span><span>{systemSession?.sessionMetadata.providerName ?? '-'}</span><span>{systemSession?.sessionMetadata.hardwareRole ?? '-'}</span></div>
              <small className="muted">该文件包含 topics / service-action events / trace correlation，可用于 release audit、acceptance review 与故障复盘。</small>
            </div>
          ) : (
            <div className="diff-box">
              <strong>浏览器离线回放边界</strong>
              <small className="muted">该文件仅覆盖浏览器日志、命令、趋势和检查器记录，不能替代系统级 replay 证据包。</small>
            </div>
          )}
          <div className="replay-slider-row">
            <input type="range" min={0} max={Math.max(0, rows.length - 1)} value={replay.activeLogIndex} onChange={(event) => setReplayIndex(Number(event.target.value))} />
            <span className="muted">{Math.round(progress * 100)}%</span>
          </div>
          <div className="kv-grid compact-grid">
            <div className="kv-item"><span>延迟样本</span><strong>{replay.session.history.latency[historyIndex] ?? 0} ms</strong></div>
            <div className="kv-item"><span>电量样本</span><strong>{replay.session.history.battery[historyIndex] ?? 0} %</strong></div>
            <div className="kv-item"><span>左轮样本</span><strong>{formatNumber(replay.session.history.leftWheel[historyIndex] ?? 0, 2)}</strong></div>
            <div className="kv-item"><span>右轮样本</span><strong>{formatNumber(replay.session.history.rightWheel[historyIndex] ?? 0, 2)}</strong></div>
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
            </div>
          ) : null}
        </>
      ) : null}
    </SectionCard>
  );
}
