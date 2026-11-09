import type { ReactNode } from 'react';
import { splitHighlights } from '../lib/format';

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
        <div key={i} className="skeleton" style={{ width: `${92 - i * 15}%` }} />
      ))}
    </div>
  );
}

export function Spinner({ label = 'Working' }: { label?: string }) {
  return <span className="spinner" role="status" aria-label={label} />;
}

export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="notice error" role="alert">
      {error instanceof Error ? error.message : 'Something went wrong'}
      {retry && (
        <button className="btn btn-ghost btn-sm" onClick={retry} style={{ marginLeft: 8 }}>
          Retry
        </button>
      )}
    </div>
  );
}

/** Render an FTS snippet: highlight markers become <mark>, everything else stays text. */
export function Highlighted({ snippet }: { snippet: string }) {
  return (
    <>
      {splitHighlights(snippet).map((part, i) => (part.hit ? <mark key={i}>{part.text}</mark> : <span key={i}>{part.text}</span>))}
    </>
  );
}
