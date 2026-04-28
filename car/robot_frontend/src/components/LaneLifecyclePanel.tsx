import { useMemo, useState } from 'react';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import {
  defaultVisibleLaneEntries,
  hiddenByDefaultLaneEntries,
  lifecycleLabel,
  lifecycleTone,
} from '@/governance/runtimeGovernance';

export function LaneLifecyclePanel() {
  const [showHidden, setShowHidden] = useState(false);
  const defaultVisible = useMemo(() => defaultVisibleLaneEntries(), []);
  const hidden = useMemo(() => hiddenByDefaultLaneEntries(), []);
  const rows = showHidden ? [...defaultVisible, ...hidden] : defaultVisible;

  return (
    <SectionCard
      title="Lane 生命周期 / 默认暴露"
      right={
        <div className="toolbar-inline">
          <StatusPill label={showHidden ? '包含隐藏 lane' : '仅主线默认暴露'} tone={showHidden ? 'warning' : 'success'} />
          <button className="ghost-btn small-btn" onClick={() => setShowHidden((value) => !value)}>
            {showHidden ? '收起实验/回滚 lane' : '显示实验/回滚 lane'}
          </button>
        </div>
      }
    >
      <div className="diff-box compact-box">
        <strong>默认规则</strong>
        <p className="muted">正常操作面默认只展示 default_visible 的主线 lane。实验与回滚 lane 默认隐藏，只有显式展开后才显示治理说明。</p>
      </div>
      <div className="history-list">
        {rows.map((lane) => (
          <div key={lane.laneId} className="log-item">
            <div className="log-head">
              <strong>{lane.laneId}</strong>
              <StatusPill label={lifecycleLabel(lane.lifecycleStage)} tone={lifecycleTone(lane.lifecycleStage)} />
            </div>
            <p>{lane.description}</p>
            <div className="kv-grid compact-grid">
              <div className="kv-item"><span>owner</span><strong>{lane.owner}</strong></div>
              <div className="kv-item"><span>默认暴露</span><strong>{lane.defaultSurfaceExposure}</strong></div>
              <div className="kv-item"><span>保留条件</span><strong>{lane.retentionCondition}</strong></div>
              <div className="kv-item"><span>退出条件</span><strong>{lane.exitCondition}</strong></div>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
