import { useState, type FormEvent } from 'react';

interface Props {
  tags: string[];
  suggestions?: string[];
  onChange: (tags: string[]) => void;
  busy?: boolean;
}

/** Add/remove tags; suggested tags (from a summary) can be added with one click. */
export function TagEditor({ tags, suggestions = [], onChange, busy }: Props) {
  const [draft, setDraft] = useState('');
  const pending = suggestions.filter((s) => !tags.includes(s));

  function add(e: FormEvent) {
    e.preventDefault();
    const name = draft.trim();
    if (!name) return;
    onChange([...tags, name]);
    setDraft('');
  }

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
        {tags.length === 0 && <span className="muted" style={{ fontSize: '0.88rem' }}>No tags yet.</span>}
        {tags.map((t) => (
          <button key={t} className="stamp" disabled={busy} onClick={() => onChange(tags.filter((x) => x !== t))} aria-label={`Remove tag ${t}`} title="Remove tag">
            {t} ✕
          </button>
        ))}
      </div>
      <form onSubmit={add} style={{ display: 'flex', gap: 6 }}>
        <input className="input" style={{ padding: '6px 10px' }} placeholder="Add a tag" aria-label="New tag" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={40} />
        <button className="btn btn-sm" disabled={busy || !draft.trim()}>
          Add
        </button>
      </form>
      {pending.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Suggested:</span>
          {pending.map((s) => (
            <button key={s} className="stamp brass" disabled={busy} onClick={() => onChange([...tags, s])} aria-label={`Add suggested tag ${s}`}>
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
