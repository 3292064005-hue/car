export {
  BRIDGE_CAPABILITIES,
  COMPATIBILITY_MODES,
  PROTOCOL_VERSION,
  SCHEMA_VERSION,
  TRANSPORT_PROTOCOL_VERSION,
  UART_PROTOCOL_VERSION,
  WEB_PROTOCOL_VERSION,
  WEB_SCHEMA_VERSION
} from '@/generated/bridgeContract';
import type {
  CommandType,
  DashboardLayouts,
  DashboardPreset,
  LogDomain,
  PanelId,
  ParamProfile,
  RobotMode,
  WaypointStatus
} from '@/types/robot';

export const NAV_ITEMS: Array<{ path: string; label: string }> = [
  { path: '/', label: '主控台' },
  { path: '/teleop', label: '手动控制' },
  { path: '/patrol', label: '巡检任务' },
  { path: '/perception', label: '视觉语音' },
  { path: '/safety', label: '安全参数' },
  { path: '/replay', label: '会话回放' },
  { path: '/inspector', label: 'Bridge 检查器' },
  { path: '/reports', label: '运行报告' }
];

export const MODE_ORDER: RobotMode[] = ['BOOT', 'IDLE', 'MANUAL', 'PATROL', 'TRACK', 'SAFE_STOP', 'FAULT'];

export const DEFAULT_PARAMS: ParamProfile = {
  maxLinearSpeed: 0.45,
  maxAngularSpeed: 1.1,
  teleopStep: 0.08,
  trackOffsetDeadband: 0.1,
  lowPowerThreshold: 25,
  reconnectTimeoutMs: 1500
};

export const DEFAULT_WAYPOINTS: WaypointStatus[] = [
  { id: 'P1', label: '巡检点 P1', status: 'pending' },
  { id: 'P2', label: '巡检点 P2', status: 'pending' },
  { id: 'P3', label: '巡检点 P3', status: 'pending' },
  { id: 'P4', label: '巡检点 P4', status: 'pending' }
];

export const WS_URL = import.meta.env.VITE_ROBOT_WS_URL ?? '';
export const MJPEG_URL = import.meta.env.VITE_ROBOT_MJPEG_URL ?? '';
export const ENABLE_MOCK = (import.meta.env.VITE_ENABLE_MOCK ?? 'true') === 'true';
export const DEMO_READONLY = (import.meta.env.VITE_READONLY_DEMO ?? 'false') === 'true';
export const BRIDGE_LABEL = import.meta.env.VITE_BRIDGE_LABEL ?? 'robot-bridge-local';


export const COMMAND_TIMEOUT_MS = 2500;
export const HISTORY_LIMIT = 48;
export const LOG_LIMIT = 400;
export const TRACE_LIMIT = 220;

export const STALE_THRESHOLDS_MS = {
  motion: 1000,
  power: 2500,
  vision: 1600,
  voice: 3000,
  heartbeat: 1200
};

export const PARAM_PRESETS: Record<string, ParamProfile> = {
  室内保守: {
    maxLinearSpeed: 0.26,
    maxAngularSpeed: 0.7,
    teleopStep: 0.06,
    trackOffsetDeadband: 0.12,
    lowPowerThreshold: 28,
    reconnectTimeoutMs: 1800
  },
  演示标准: DEFAULT_PARAMS,
  快速调试: {
    maxLinearSpeed: 0.55,
    maxAngularSpeed: 1.25,
    teleopStep: 0.1,
    trackOffsetDeadband: 0.09,
    lowPowerThreshold: 22,
    reconnectTimeoutMs: 1200
  }
};

export const DANGEROUS_COMMANDS: CommandType[] = ['estop', 'set_mode', 'start_patrol', 'teleop_cmd'];
export const LOG_DOMAINS: Array<'ALL' | LogDomain> = ['ALL', 'SYSTEM', 'BRIDGE', 'CONTROL', 'VISION', 'VOICE', 'TASK', 'SAFETY', 'PARAM', 'REPLAY', 'INSPECTOR', 'REPORT'];

export const PANEL_PRESETS: Record<DashboardPreset, PanelId[]> = {
  demo: ['connection', 'mode', 'video', 'power', 'vision', 'fault', 'reports'],
  ops: ['connection', 'mode', 'video', 'power', 'chassis', 'vision', 'voice', 'fault', 'commands', 'patrol', 'reports', 'logs'],
  debug: ['connection', 'mode', 'video', 'power', 'chassis', 'vision', 'voice', 'fault', 'commands', 'history', 'logs', 'layout', 'patrol', 'inspector', 'replay', 'reports']
};

export const PANEL_LABELS: Record<PanelId, string> = {
  connection: '连接状态',
  mode: '模式状态',
  video: '视频主视图',
  power: '电源状态',
  chassis: '底盘遥测',
  vision: '视觉结果',
  voice: '语音事件',
  fault: '故障状态',
  commands: '命令队列',
  logs: '事件日志',
  history: '趋势条带',
  layout: '布局控制',
  patrol: '巡检任务',
  inspector: 'Bridge 检查器',
  replay: '会话回放',
  reports: '运行摘要'
};

export const DEFAULT_PANEL_VISIBILITY: Record<PanelId, boolean> = {
  connection: true,
  mode: true,
  video: true,
  power: true,
  chassis: true,
  vision: true,
  voice: true,
  fault: true,
  commands: true,
  logs: true,
  history: true,
  layout: true,
  patrol: true,
  inspector: true,
  replay: true,
  reports: true
};

export const DEFAULT_DASHBOARD_LAYOUTS: DashboardLayouts = {
  demo: [
    { id: 'connection', order: 0, colSpan: 1, rowSpan: 1 },
    { id: 'mode', order: 1, colSpan: 1, rowSpan: 1 },
    { id: 'video', order: 2, colSpan: 2, rowSpan: 2 },
    { id: 'power', order: 3, colSpan: 1, rowSpan: 1 },
    { id: 'vision', order: 4, colSpan: 1, rowSpan: 1 },
    { id: 'fault', order: 5, colSpan: 1, rowSpan: 1 },
    { id: 'reports', order: 6, colSpan: 1, rowSpan: 1 }
  ],
  ops: [
    { id: 'connection', order: 0, colSpan: 1, rowSpan: 1 },
    { id: 'mode', order: 1, colSpan: 1, rowSpan: 1 },
    { id: 'video', order: 2, colSpan: 2, rowSpan: 2 },
    { id: 'commands', order: 3, colSpan: 1, rowSpan: 1 },
    { id: 'power', order: 4, colSpan: 1, rowSpan: 1 },
    { id: 'chassis', order: 5, colSpan: 1, rowSpan: 1 },
    { id: 'vision', order: 6, colSpan: 1, rowSpan: 1 },
    { id: 'voice', order: 7, colSpan: 1, rowSpan: 1 },
    { id: 'patrol', order: 8, colSpan: 1, rowSpan: 1 },
    { id: 'reports', order: 9, colSpan: 1, rowSpan: 1 },
    { id: 'fault', order: 10, colSpan: 1, rowSpan: 1 },
    { id: 'logs', order: 11, colSpan: 2, rowSpan: 1 }
  ],
  debug: [
    { id: 'connection', order: 0, colSpan: 1, rowSpan: 1 },
    { id: 'mode', order: 1, colSpan: 1, rowSpan: 1 },
    { id: 'video', order: 2, colSpan: 2, rowSpan: 2 },
    { id: 'layout', order: 3, colSpan: 1, rowSpan: 1 },
    { id: 'commands', order: 4, colSpan: 1, rowSpan: 1 },
    { id: 'power', order: 5, colSpan: 1, rowSpan: 1 },
    { id: 'chassis', order: 6, colSpan: 1, rowSpan: 1 },
    { id: 'vision', order: 7, colSpan: 1, rowSpan: 1 },
    { id: 'voice', order: 8, colSpan: 1, rowSpan: 1 },
    { id: 'fault', order: 9, colSpan: 1, rowSpan: 1 },
    { id: 'history', order: 10, colSpan: 1, rowSpan: 1 },
    { id: 'patrol', order: 11, colSpan: 1, rowSpan: 1 },
    { id: 'reports', order: 12, colSpan: 1, rowSpan: 1 },
    { id: 'inspector', order: 13, colSpan: 2, rowSpan: 2 },
    { id: 'replay', order: 14, colSpan: 2, rowSpan: 2 },
    { id: 'logs', order: 15, colSpan: 2, rowSpan: 2 }
  ]
};

export const MOCK_SCENARIOS = [
  { id: 'low-power', label: '低压告警' },
  { id: 'heartbeat-drop', label: '心跳中断' },
  { id: 'fault-lock', label: '故障锁定' },
  { id: 'ack-timeout', label: 'ACK 超时' },
  { id: 'patrol-interrupt', label: '巡检中断' },
  { id: 'qr-burst', label: '二维码连发' },
  { id: 'estop-latch', label: '急停锁定' },
  { id: 'voice-burst', label: '语音连发' }
] as const;
