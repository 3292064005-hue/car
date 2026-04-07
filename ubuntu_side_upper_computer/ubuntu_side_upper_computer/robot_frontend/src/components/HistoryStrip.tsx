import { getHistoryMax } from '@/shared/utils';

export function HistoryStrip({ values, suffix = '' }: { values: number[]; suffix?: string }) {
  const max = getHistoryMax(values);
  return (
    <div className="history-strip">
      {values.length === 0 ? <span className="muted">暂无历史样本</span> : null}
      {values.map((value, index) => (
        <div key={`${index}-${value}`} className="history-bar" style={{ height: `${Math.max(8, (value / max) * 100)}%` }} title={`${value}${suffix}`} />
      ))}
    </div>
  );
}
