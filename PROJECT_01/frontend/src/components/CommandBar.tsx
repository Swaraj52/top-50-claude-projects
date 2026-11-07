import { useMemo, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useEmailMutations, useEventMutations, useGenerateBriefing, useReminderMutations, useTaskMutations, useTz } from '../api/hooks';
import { dateOf, fmtLongDate, fmtTime } from '../lib/dates';
import { parseQuickAdd, type QuickKind } from '../lib/quickAdd';
import { Dialog } from './Dialog';
import { useFeedback } from './feedback';

const KINDS: { value: QuickKind | 'auto'; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'task', label: 'Task' },
  { value: 'reminder', label: 'Reminder' },
  { value: 'event', label: 'Event' },
];

export function CommandBar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} className="command">
      {open && <CommandBody onClose={onClose} />}
    </Dialog>
  );
}

function CommandBody({ onClose }: { onClose: () => void }) {
  const tz = useTz();
  const navigate = useNavigate();
  const { toast } = useFeedback();
  const tasks = useTaskMutations();
  const reminders = useReminderMutations();
  const events = useEventMutations();
  const briefing = useGenerateBriefing();
  const email = useEmailMutations();
  const [text, setText] = useState('');
  const [kind, setKind] = useState<QuickKind | 'auto'>('auto');
  const [busy, setBusy] = useState(false);

  const parsed = useMemo(
    () => (text.trim() ? parseQuickAdd(text, tz, kind === 'auto' ? undefined : kind) : null),
    [text, tz, kind],
  );

  async function submit() {
    if (!parsed || parsed.error || busy) return;
    setBusy(true);
    try {
      if (parsed.kind === 'task') {
        await tasks.create.mutateAsync({ title: parsed.title, priority: parsed.priority, due_date: parsed.dueDate });
      } else if (parsed.kind === 'reminder') {
        await reminders.create.mutateAsync({ text: parsed.title, remind_at: parsed.start! });
      } else {
        await events.create.mutateAsync({ title: parsed.title, start_at: parsed.start!, end_at: parsed.end!, all_day: parsed.allDay });
      }
      toast({ title: `${parsed.kind[0].toUpperCase()}${parsed.kind.slice(1)} added`, body: parsed.title });
      onClose();
    } catch (err) {
      toast({ title: 'Could not add it', body: errorMessage(err), tone: 'error' });
    } finally {
      setBusy(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  }

  const run = (fn: () => Promise<unknown>, done: string) => async () => {
    onClose();
    try {
      await fn();
      toast({ title: done });
    } catch (err) {
      toast({ title: 'That didn’t work', body: errorMessage(err), tone: 'error' });
    }
  };

  const go = (path: string) => () => {
    onClose();
    navigate(path);
  };

  const actions = [
    { label: 'Generate today’s briefing', hint: 'Action', run: run(() => briefing.mutateAsync(), 'Briefing ready') },
    { label: 'Sync email', hint: 'Action', run: run(() => email.sync.mutateAsync(), 'Email synced') },
    { label: 'Open tasks', hint: 'Go to', run: go('/tasks') },
    { label: 'Open calendar', hint: 'Go to', run: go('/calendar') },
    { label: 'Open settings', hint: 'Go to', run: go('/settings') },
  ];

  return (
    <div>
      <label className="sr-only" htmlFor="quick-add">
        Quick add a task, reminder or event
      </label>
      <input
        id="quick-add"
        className="command-input"
        placeholder="Add anything… “Call bank tomorrow 10am !high”"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        autoFocus
        autoComplete="off"
      />
      <div className="command-bar">
        <div className="segmented" role="group" aria-label="Type">
          {KINDS.map((k) => (
            <button key={k.value} type="button" aria-pressed={kind === k.value} onClick={() => setKind(k.value)}>
              {k.label}
            </button>
          ))}
        </div>
        <span className="muted" style={{ fontSize: '0.75rem' }}>
          <span className="kbd">Enter</span> add · <span className="kbd">Esc</span> close
        </span>
      </div>

      {parsed ? (
        <dl className="preview" aria-live="polite">
          <dt>Type</dt>
          <dd>
            <strong style={{ textTransform: 'capitalize' }}>{parsed.kind}</strong>
          </dd>
          <dt>Title</dt>
          <dd>{parsed.title || <span className="muted">—</span>}</dd>
          <dt>When</dt>
          <dd className="mono">
            {parsed.kind === 'task' && (parsed.dueDate ? `Due ${fmtLongDate(parsed.dueDate)}` : 'No due date')}
            {parsed.kind !== 'task' && parsed.start &&
              `${fmtLongDate(dateOf(parsed.start, tz))}${parsed.allDay ? ' · all day' : ` · ${fmtTime(parsed.start, tz)}`}${
                parsed.kind === 'event' && parsed.end && !parsed.allDay ? `–${fmtTime(parsed.end, tz)}` : ''
              }`}
            {parsed.kind !== 'task' && !parsed.start && '—'}
          </dd>
          {parsed.kind === 'task' && (
            <>
              <dt>Priority</dt>
              <dd style={{ textTransform: 'capitalize' }}>{parsed.priority}</dd>
            </>
          )}
          {parsed.error && (
            <dd style={{ gridColumn: '1 / -1' }} className="field-error" role="alert">
              {parsed.error}
            </dd>
          )}
          <dd style={{ gridColumn: '1 / -1', marginTop: 6 }}>
            <button className="btn btn-primary btn-sm" onClick={submit} disabled={!!parsed.error || busy}>
              {busy ? 'Adding…' : `Add ${parsed.kind}`}
            </button>
          </dd>
        </dl>
      ) : (
        <>
          <ul className="command-actions" aria-label="Actions">
            {actions.map((a) => (
              <li key={a.label}>
                <button onClick={a.run}>
                  <span>{a.label}</span>
                  <span className="muted mono" style={{ fontSize: '0.72rem' }}>
                    {a.hint}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="command-hint">
            Try “remind me to stretch in 45 minutes”, “event Lunch with Sam fri 1-2pm” or “Pay rent on the 1st !high”.
          </div>
        </>
      )}
    </div>
  );
}
