import {
  DEFAULT_DASHBOARD_LAYOUTS,
  PANEL_PRESETS,
} from '@/shared/constants';
import type { DashboardPanelConfig, DashboardPreset, PanelId } from '@/types/robot';
import { cloneLayouts, makeLog } from '@/store/defaults';
import { inferBreakpoint, mergeLayoutVisibility } from '@/store/helpers';
import { moveItem, normalizePanelOrder } from '@/shared/utils';
import type { RobotStore } from '@/store/model';
import type { RobotStoreSlice } from './types';
import { LOG_LIMIT as MAX_LOGS } from '@/shared/constants';

export function createUiSlice(set: Parameters<RobotStoreSlice<RobotStore>>[0]): Pick<RobotStore, 'setUiFilter' | 'applyDashboardPreset' | 'togglePanelVisibility' | 'setPanelSpan' | 'setPanelRowSpan' | 'movePanel' | 'reorderPanel' | 'resetLayoutPreset' | 'importDashboardLayouts' | 'toggleLayoutLock' | 'setActiveBreakpoint'> {
  return {
    setUiFilter: (patch) => set((state) => ({ ui: { ...state.ui, ...patch } })),
    applyDashboardPreset: (preset) =>
      set((state) => ({
        ui: {
          ...state.ui,
          dashboardPreset: preset,
          panelVisibility: {
            ...state.ui.panelVisibility,
            ...Object.fromEntries((Object.keys(state.ui.panelVisibility) as PanelId[]).map((key) => [key, PANEL_PRESETS[preset].includes(key)])),
          },
        },
      })),
    togglePanelVisibility: (panelId) =>
      set((state) => ({
        ui: {
          ...state.ui,
          panelVisibility: {
            ...state.ui.panelVisibility,
            [panelId]: !state.ui.panelVisibility[panelId],
          },
        },
      })),
    setPanelSpan: (panelId, colSpan) =>
      set((state) => ({
        ui: {
          ...state.ui,
          dashboardLayouts: {
            ...state.ui.dashboardLayouts,
            [state.ui.dashboardPreset]: normalizePanelOrder(
              state.ui.dashboardLayouts[state.ui.dashboardPreset].map((item) => (item.id === panelId ? { ...item, colSpan } : item)),
            ),
          },
        },
      })),
    setPanelRowSpan: (panelId, rowSpan) =>
      set((state) => ({
        ui: {
          ...state.ui,
          dashboardLayouts: {
            ...state.ui.dashboardLayouts,
            [state.ui.dashboardPreset]: normalizePanelOrder(
              state.ui.dashboardLayouts[state.ui.dashboardPreset].map((item) => (item.id === panelId ? { ...item, rowSpan } : item)),
            ),
          },
        },
      })),
    movePanel: (panelId, direction) =>
      set((state) => {
        const preset = state.ui.dashboardPreset;
        const layout = [...state.ui.dashboardLayouts[preset]].sort((a, b) => a.order - b.order);
        const index = layout.findIndex((item) => item.id === panelId);
        const nextIndex = direction === 'up' ? Math.max(0, index - 1) : Math.min(layout.length - 1, index + 1);
        return {
          ui: {
            ...state.ui,
            dashboardLayouts: {
              ...state.ui.dashboardLayouts,
              [preset]: normalizePanelOrder(moveItem(layout, index, nextIndex)),
            },
          },
        };
      }),
    reorderPanel: (sourceId, targetId) =>
      set((state) => {
        const preset = state.ui.dashboardPreset;
        const layout = [...state.ui.dashboardLayouts[preset]].sort((a, b) => a.order - b.order);
        const sourceIndex = layout.findIndex((item) => item.id === sourceId);
        const targetIndex = layout.findIndex((item) => item.id === targetId);
        if (sourceIndex < 0 || targetIndex < 0) return state;
        return {
          ui: {
            ...state.ui,
            dashboardLayouts: {
              ...state.ui.dashboardLayouts,
              [preset]: normalizePanelOrder(moveItem(layout, sourceIndex, targetIndex)),
            },
          },
        };
      }),
    resetLayoutPreset: (preset) =>
      set((state) => {
        const targetPreset = preset ?? state.ui.dashboardPreset;
        const dashboardLayouts = cloneLayouts(state.ui.dashboardLayouts);
        dashboardLayouts[targetPreset] = cloneLayouts(DEFAULT_DASHBOARD_LAYOUTS)[targetPreset];
        return {
          ui: {
            ...state.ui,
            dashboardLayouts,
            panelVisibility: mergeLayoutVisibility(dashboardLayouts, state.ui.panelVisibility, targetPreset),
          },
        };
      }),
    importDashboardLayouts: (layouts) =>
      set((state) => {
        const dashboardLayouts = cloneLayouts(state.ui.dashboardLayouts);
        (Object.keys(layouts) as DashboardPreset[]).forEach((preset) => {
          if (!layouts[preset]) return;
          dashboardLayouts[preset] = normalizePanelOrder(layouts[preset] as DashboardPanelConfig[]);
        });
        return {
          ui: {
            ...state.ui,
            dashboardLayouts,
            panelVisibility: mergeLayoutVisibility(dashboardLayouts, state.ui.panelVisibility, state.ui.dashboardPreset),
          },
          logs: [makeLog('INFO', 'SYSTEM', '已导入布局配置。'), ...state.logs].slice(0, MAX_LOGS),
        };
      }),
    toggleLayoutLock: () => set((state) => ({ ui: { ...state.ui, lockedLayout: !state.ui.lockedLayout } })),
    setActiveBreakpoint: (width) => set((state) => ({ ui: { ...state.ui, activeBreakpoint: inferBreakpoint(width) } })),
  };
}
