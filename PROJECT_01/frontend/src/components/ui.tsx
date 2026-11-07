import type { ReactNode } from 'react';
import type { Priority } from '../api/types';

export function Section({ title, count, action, children }: { title: string; count?: ReactNode; action?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <div className="section-head">
        <h2>{title}</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          {count !== undefined && <span className="count">{count}</span>}
          {action}
        </div>
      </div>
      {children}
    </section>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
      {action && <div>{action}</div>}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${90 - i * 17}%` }} />
      ))}
    </div>
  );
}

export function Spinner({ label = 'Working' }: { label?: string }) {
  return <span className="spinner" role="status" aria-label={label} />;
}

export function PriorityDot({ priority }: { priority: Priority }) {
  return <span className={`prio ${priority}`} title={`${priority} priority`} aria-label={`${priority} priority`} />;
}

export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="notice error" role="alert">
      {error instanceof Error ? error.message : 'Something went wrong'}
      {retry && (
        <button className="btn btn-sm btn-ghost" onClick={retry} style={{ marginLeft: 8 }}>
          Retry
        </button>
      )}
    </div>
  );
}
