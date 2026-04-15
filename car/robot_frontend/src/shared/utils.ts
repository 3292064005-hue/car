import type {
  CommandRecord,
  DashboardPanelConfig,
  DashboardPreset,
  HistoryState,
  InspectorRecord,
  LogItem,
  ParamProfile,
  ReplaySession
} from '@/types/robot';

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function formatNumber(value: number, digits = 2): string {
  return Number.isFinite(value) ? value.toFixed(digits) : '--';
}

export function formatTimestamp(input: string | null): string {
  if (!input) return '--';
  const date = new Date(input);
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleTimeString('zh-CN', { hour12: false });
}

export function formatDateTime(input: string | null): string {
  if (!input) return '--';
  const date = new Date(input);
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false });
}

export function formatRelativeAge(input: string | null, now = Date.now()): string {
  if (!input) return '--';
  const value = new Date(input).getTime();
  if (Number.isNaN(value)) return '--';
  return `${Math.max(0, Math.round((now - value) / 100)) / 10}s 前`;
}

export function uuid(prefix = 'id'): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

export function pushHistory(history: number[], next: number, limit: number): number[] {
  const merged = [...history, next];
  return merged.slice(Math.max(0, merged.length - limit));
}

export function moveItem<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  if (fromIndex < 0 || toIndex < 0 || fromIndex >= items.length || toIndex >= items.length || fromIndex === toIndex) return items;
  const clone = [...items];
  const [item] = clone.splice(fromIndex, 1);
  clone.splice(toIndex, 0, item);
  return clone;
}

export function normalizePanelOrder(layout: DashboardPanelConfig[]): DashboardPanelConfig[] {
  return [...layout]
    .sort((a, b) => a.order - b.order)
    .map((item, index) => ({ ...item, order: index }));
}

export function downloadText(filename: string, text: string, mime = 'text/plain;charset=utf-8'): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function exportLogsAsCsv(logs: LogItem[]): string {
  const head = 'timestamp,level,domain,message,details';
  const rows = logs.map((item) =>
    [item.timestamp, item.level, item.domain, item.message, item.details ?? '']
      .map((value) => `"${String(value).replace(/"/g, '""')}"`)
      .join(',')
  );
  return [head, ...rows].join('\n');
}

export function exportCommandsAsCsv(commands: CommandRecord[]): string {
  const head = 'createdAt,type,status,summary,priority,dangerous,ackLatencyMs,error';
  const rows = commands.map((item) =>
    [item.createdAt, item.type, item.status, item.summary, item.priority, item.dangerous, item.ackLatencyMs ?? '', item.error ?? '']
      .map((value) => `"${String(value).replace(/"/g, '""')}"`)
      .join(',')
  );
  return [head, ...rows].join('\n');
}

export function deepCloneParams(input: ParamProfile): ParamProfile {
  return JSON.parse(JSON.stringify(input)) as ParamProfile;
}

export function summarizeParamDiff(applied: ParamProfile, draft: ParamProfile): string[] {
  return (Object.keys(applied) as Array<keyof ParamProfile>)
    .filter((key) => applied[key] !== draft[key])
    .map((key) => `${String(key)}: ${applied[key]} -> ${draft[key]}`);
}

export function getHistoryMax(history: number[]): number {
  return history.length ? Math.max(...history, 1) : 1;
}

export function average(values: number[]): number {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

export function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((p / 100) * (sorted.length - 1))));
  return sorted[index];
}

export function toJson(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

export function safeNowIso(): string {
  return new Date().toISOString();
}

export function buildSessionExport(logs: LogItem[], history: HistoryState, params: unknown, inspectorTrace: InspectorRecord[] = [], commands: CommandRecord[] = []): string {
  return toJson({
    kind: 'offline-session-export',
    exportScope: 'frontend-state-snapshot',
    exportedAt: safeNowIso(),
    sourceName: 'robot-console',
    version: '4.1.0',
    logs,
    history,
    params,
    inspectorTrace,
    commands
  });
}

export function parseReplaySession(raw: string): ReplaySession | null {
  try {
    const parsed = JSON.parse(raw) as ReplaySession;
    if (!parsed || typeof parsed !== 'object') return null;
    if (parsed.kind !== 'offline-session-export') return null;
    if (!Array.isArray(parsed.logs) || !parsed.history || !parsed.params) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function summarizeInspectorRaw(raw: unknown): string {
  if (typeof raw === 'string') return raw;
  return toJson(raw);
}

export function safeClipboardWrite(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  downloadText('clipboard-fallback.txt', text);
  return Promise.resolve();
}

export function parseImportedLayout(raw: string): Partial<Record<DashboardPreset, DashboardPanelConfig[]>> | null {
  try {
    const parsed = JSON.parse(raw) as Partial<Record<DashboardPreset, DashboardPanelConfig[]>>;
    return parsed;
  } catch {
    return null;
  }
}
