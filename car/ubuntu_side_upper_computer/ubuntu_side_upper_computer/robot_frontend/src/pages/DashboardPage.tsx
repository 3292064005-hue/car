import { useEffect, useMemo, useState } from 'react';
import { BridgeInspectorPanel } from '@/components/BridgeInspectorPanel';
import { ChassisPanel } from '@/components/ChassisPanel';
import { CommandQueuePanel } from '@/components/CommandQueuePanel';
import { ConnectionPanel } from '@/components/ConnectionPanel';
import { FaultPanel } from '@/components/FaultPanel';
import { HistoryPanel } from '@/components/HistoryPanel';
import { LayoutPanel } from '@/components/LayoutPanel';
import { LogPanel } from '@/components/LogPanel';
import { ModePanel } from '@/components/ModePanel';
import { PatrolPanel } from '@/components/PatrolPanel';
import { PowerPanel } from '@/components/PowerPanel';
import { ReplayPanel } from '@/components/ReplayPanel';
import { ReportSummaryPanel } from '@/components/ReportSummaryPanel';
import { SummaryRibbon } from '@/components/SummaryRibbon';
import { VideoPanel } from '@/components/VideoPanel';
import { VisionPanel } from '@/components/VisionPanel';
import { VoicePanel } from '@/components/VoicePanel';
import { PANEL_LABELS } from '@/shared/constants';
import { cn } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';
import type { PanelId } from '@/types/robot';

const panelRegistry: Record<PanelId, React.ReactNode> = {
  connection: <ConnectionPanel />,
  mode: <ModePanel />,
  video: <VideoPanel />,
  power: <PowerPanel />,
  chassis: <ChassisPanel />,
  vision: <VisionPanel />,
  voice: <VoicePanel />,
  fault: <FaultPanel />,
  commands: <CommandQueuePanel />,
  logs: <LogPanel />,
  history: <HistoryPanel />,
  layout: <LayoutPanel />,
  patrol: <PatrolPanel />,
  inspector: <BridgeInspectorPanel />,
  replay: <ReplayPanel />,
  reports: <ReportSummaryPanel />
};

export default function DashboardPage() {
  const ui = useRobotStore((state) => state.ui);
  const setActiveBreakpoint = useRobotStore((state) => state.setActiveBreakpoint);
  const reorderPanel = useRobotStore((state) => state.reorderPanel);
  const visiblePanels = useMemo(
    () => ui.dashboardLayouts[ui.dashboardPreset].filter((item) => ui.panelVisibility[item.id]).sort((a, b) => a.order - b.order),
    [ui.dashboardLayouts, ui.dashboardPreset, ui.panelVisibility]
  );
  const [draggingId, setDraggingId] = useState<PanelId | null>(null);

  useEffect(() => {
    const update = () => setActiveBreakpoint(window.innerWidth);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [setActiveBreakpoint]);

  const columnCount = ui.activeBreakpoint === 'compact' ? 1 : ui.activeBreakpoint === 'normal' ? 2 : 3;

  return (
    <div className="page-stack">
      <SummaryRibbon />
      <div className="dashboard-v4-header">
        <div>
          <strong>布局预设：</strong>{ui.dashboardPreset} / <strong>断点：</strong>{ui.activeBreakpoint}
        </div>
        <div className="muted">支持面板显隐、拖拽重排、跨度调整和布局导入导出。</div>
      </div>
      <div className="dashboard-grid-v4" style={{ ['--dashboard-columns' as string]: String(columnCount) }}>
        {visiblePanels.map((panel) => {
          const effectiveSpan = Math.min(panel.colSpan, columnCount) as 1 | 2 | 3;
          return (
            <div
              key={panel.id}
              className={cn('dashboard-panel-cell', draggingId === panel.id ? 'dragging' : '')}
              style={{ gridColumn: `span ${effectiveSpan}`, gridRow: `span ${panel.rowSpan}` }}
              draggable={!ui.lockedLayout}
              onDragStart={() => setDraggingId(panel.id)}
              onDragEnd={() => setDraggingId(null)}
              onDragOver={(event) => {
                if (ui.lockedLayout) return;
                event.preventDefault();
              }}
              onDrop={(event) => {
                if (ui.lockedLayout) return;
                event.preventDefault();
                if (draggingId && draggingId !== panel.id) reorderPanel(draggingId, panel.id);
                setDraggingId(null);
              }}
            >
              <div className="dashboard-panel-caption">
                <span>{PANEL_LABELS[panel.id]}</span>
                {!ui.lockedLayout ? <small>可拖拽</small> : <small>布局已锁定</small>}
              </div>
              {panelRegistry[panel.id]}
            </div>
          );
        })}
      </div>
    </div>
  );
}
