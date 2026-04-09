import type { PropsWithChildren, ReactNode } from 'react';
import { cn } from '@/shared/utils';

interface SectionCardProps extends PropsWithChildren {
  title: string;
  right?: ReactNode;
  compact?: boolean;
  className?: string;
}

export function SectionCard({ title, right, children, compact, className }: SectionCardProps) {
  return (
    <section className={cn('card', className)}>
      <header className="card-header">
        <h3>{title}</h3>
        {right ? <div>{right}</div> : null}
      </header>
      <div className={cn('card-body', compact ? 'compact' : '')}>{children}</div>
    </section>
  );
}
