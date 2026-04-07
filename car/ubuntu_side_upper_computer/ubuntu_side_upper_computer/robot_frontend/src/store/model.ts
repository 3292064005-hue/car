import type {
  BridgeInboundEvent,
  CommandRecord,
  CommandStatus,
  CommandType,
  ConnectionState,
  DashboardLayouts,
  DashboardPanelConfig,
  DashboardPreset,
  FaultState,
  HistoryState,
  InspectorRecord,
  InspectorState,
  LogItem,
  MotionState,
  PanelId,
  ParamProfile,
  PowerState,
  ReplaySession,
  ReplayState,
  RobotMode,
  RuntimeState,
  StoredProfiles,
  TaskState,
  UiState,
  VisionState,
  VoiceState,
  DashboardBreakpoint
} from '@/types/robot';

export interface SnapshotExport {
  logs: LogItem[];
  history: HistoryState;
  params: StoredProfiles;
  inspectorTrace: InspectorRecord[];
  commands: CommandRecord[];
  json: string;
}

export interface RobotStoreData {
  connection: ConnectionState;
  motion: MotionState;
  power: PowerState;
  vision: VisionState;
  voice: VoiceState;
  task: TaskState;
  fault: FaultState;
  runtime: RuntimeState;
  profiles: StoredProfiles;
  history: HistoryState;
  inspector: InspectorState;
  replay: ReplayState;
  commands: CommandRecord[];
  logs: LogItem[];
  ui: UiState;
}

export interface RobotStore extends RobotStoreData {
  setTransportInfo: (type: ConnectionState['transportType'], label: string) => void;
  markBridgeOpen: () => void;
  markBridgeClosed: () => void;
  tickRuntime: () => void;
  pushLog: (input: Pick<LogItem, 'level' | 'domain' | 'message'> & Partial<Pick<LogItem, 'details' | 'timestamp'>>) => void;
  enqueueCommand: (id: string, type: CommandType, summary: string, priority: CommandRecord['priority'], dangerous: boolean) => void;
  markCommandSent: (id: string) => void;
  markCommand: (id: string, status: CommandStatus, error?: string) => void;
  applyInboundEvent: (event: BridgeInboundEvent) => void;
  recordTrace: (direction: InspectorRecord['direction'], type: string, raw: string, verdict: InspectorRecord['verdict'], note?: string) => void;
  setUiFilter: (patch: Partial<UiState>) => void;
  applyDashboardPreset: (preset: DashboardPreset) => void;
  togglePanelVisibility: (panelId: PanelId) => void;
  setPanelSpan: (panelId: PanelId, colSpan: 1 | 2 | 3) => void;
  setPanelRowSpan: (panelId: PanelId, rowSpan: 1 | 2) => void;
  movePanel: (panelId: PanelId, direction: 'up' | 'down') => void;
  reorderPanel: (sourceId: PanelId, targetId: PanelId) => void;
  resetLayoutPreset: (preset?: DashboardPreset) => void;
  importDashboardLayouts: (layouts: Partial<DashboardLayouts>) => void;
  toggleLayoutLock: () => void;
  setActiveBreakpoint: (width: number) => void;
  setDraftParam: (key: keyof ParamProfile, value: number) => void;
  resetDraftToApplied: () => void;
  applyDraftParams: () => void;
  applyProfile: (profileName: string) => void;
  saveCurrentAsProfile: (profileName: string) => void;
  setRuntimeRejection: (reason: string | null) => void;
  loadReplaySession: (session: ReplaySession) => void;
  setReplayIndex: (index: number) => void;
  clearReplaySession: () => void;
  exportStateSnapshot: () => SnapshotExport;
}

export type { DashboardBreakpoint, DashboardPanelConfig, RobotMode };
