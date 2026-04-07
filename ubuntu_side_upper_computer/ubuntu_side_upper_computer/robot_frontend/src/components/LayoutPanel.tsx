import { Download, Lock, MoveDown, MoveUp, RotateCcw, Unlock, Upload } from 'lucide-react';
import { PANEL_LABELS } from '@/shared/constants';
import { downloadText, parseImportedLayout, toJson } from '@/shared/utils';
import { SectionCard } from '@/components/SectionCard';
import { useRobotStore } from '@/store/useRobotStore';
import type { DashboardPreset, PanelId } from '@/types/robot';

export function LayoutPanel() {
  const ui = useRobotStore((state) => state.ui);
  const applyDashboardPreset = useRobotStore((state) => state.applyDashboardPreset);
  const togglePanelVisibility = useRobotStore((state) => state.togglePanelVisibility);
  const setPanelSpan = useRobotStore((state) => state.setPanelSpan);
  const setPanelRowSpan = useRobotStore((state) => state.setPanelRowSpan);
  const movePanel = useRobotStore((state) => state.movePanel);
  const resetLayoutPreset = useRobotStore((state) => state.resetLayoutPreset);
  const importDashboardLayouts = useRobotStore((state) => state.importDashboardLayouts);
  const toggleLayoutLock = useRobotStore((state) => state.toggleLayoutLock);

  const layout = ui.dashboardLayouts[ui.dashboardPreset].sort((a, b) => a.order - b.order);

  return (
    <SectionCard
      title="布局控制"
      right={
        <div className="toolbar-inline">
          <button className="ghost-btn small-btn" onClick={() => toggleLayoutLock()}>
            {ui.lockedLayout ? <Unlock size={14} /> : <Lock size={14} />}
            {ui.lockedLayout ? '解锁布局' : '锁定布局'}
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText(`dashboard-layout-${ui.dashboardPreset}.json`, toJson(ui.dashboardLayouts), 'application/json;charset=utf-8')}>
            <Download size={14} />导出布局
          </button>
          <label className="ghost-btn small-btn">
            <Upload size={14} />导入布局
            <input
              type="file"
              accept="application/json"
              hidden
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                const text = await file.text();
                const parsed = parseImportedLayout(text);
                if (parsed) importDashboardLayouts(parsed);
              }}
            />
          </label>
        </div>
      }
    >
      <div className="inline-actions wrap-start">
        <select className="input-small" value={ui.dashboardPreset} onChange={(event) => applyDashboardPreset(event.target.value as DashboardPreset)}>
          <option value="demo">演示布局</option>
          <option value="ops">运行布局</option>
          <option value="debug">调试布局</option>
        </select>
        <button className="ghost-btn small-btn" onClick={() => resetLayoutPreset()}>
          <RotateCcw size={14} />重置当前预设
        </button>
        <div className="muted">当前断点：{ui.activeBreakpoint}，当前预设包含 {layout.length} 个已注册面板。</div>
      </div>
      <div className="layout-editor-list">
        {layout.map((panel) => (
          <div key={panel.id} className="layout-editor-item">
            <div className="layout-editor-head">
              <label className="panel-toggle-item compact-toggle">
                <input type="checkbox" checked={ui.panelVisibility[panel.id]} onChange={() => togglePanelVisibility(panel.id)} />
                <span>{PANEL_LABELS[panel.id as PanelId]}</span>
              </label>
              <div className="toolbar-inline">
                <button className="ghost-btn icon-btn" onClick={() => movePanel(panel.id, 'up')} aria-label="上移"><MoveUp size={14} /></button>
                <button className="ghost-btn icon-btn" onClick={() => movePanel(panel.id, 'down')} aria-label="下移"><MoveDown size={14} /></button>
              </div>
            </div>
            <div className="layout-editor-controls">
              <label>列跨度
                <select className="input-small" value={panel.colSpan} onChange={(event) => setPanelSpan(panel.id, Number(event.target.value) as 1 | 2 | 3)}>
                  <option value="1">1 列</option>
                  <option value="2">2 列</option>
                  <option value="3">3 列</option>
                </select>
              </label>
              <label>行跨度
                <select className="input-small" value={panel.rowSpan} onChange={(event) => setPanelRowSpan(panel.id, Number(event.target.value) as 1 | 2)}>
                  <option value="1">1 行</option>
                  <option value="2">2 行</option>
                </select>
              </label>
              <span className="muted">顺序 #{panel.order + 1}</span>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
