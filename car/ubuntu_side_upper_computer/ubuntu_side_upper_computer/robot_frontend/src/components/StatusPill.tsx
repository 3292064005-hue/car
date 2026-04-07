import { cn } from '@/shared/utils';

export function StatusPill({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' }) {
  return <span className={cn('status-pill', `tone-${tone}`)}>{label}</span>;
}
