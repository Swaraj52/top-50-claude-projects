import { useState, type FormEvent } from 'react';
import { errorMessage } from '../api/client';
import { useEventMutations, useTz } from '../api/hooks';
import type { CalendarEvent } from '../api/types';
import { addDays, dateOf, fmtLongDate, fmtTime, zonedToUtc } from '../lib/dates';
import { Dialog } from './Dialog';
import { useFeedback } from './feedback';

interface Props {
  open: boolean;
  onClose: () => void;
  event?: CalendarEvent | null;
  /** Prefill for new events: local date and start time */
  slot?: { date: string; time: string } | null;
}

export function EventForm({ open, onClose, event, slot }: Props) {
  const title = event ? (event.read_only ? event.title : 'Edit event') : 'New event';
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      {open && (event?.read_only ? <ReadOnly event={event} onClose={onClose} /> : <EventFormBody event={event ?? null} slot={slot ?? null} onClose={onClose} />)}
    </Dialog>
  );
}

function ReadOnly({ event, onClose }: { event: CalendarEvent; onClose: () => void }) {
  const tz = useTz();
  return (
    <div className="dialog-body">
      <p className="mono" style={{ marginTop: 0 }}>
        {fmtLongDate(dateOf(event.start_at, tz))}
        {event.all_day ? ' · all day' : ` · ${fmtTime(event.start_at, tz)}–${fmtTime(event.end_at, tz)}`}
      </p>
      {event.location && <p>📍 {event.location}</p>}
      {event.description && <p style={{ whiteSpace: 'pre-wrap' }}>{event.description}</p>}
      <div className="notice info">From the subscribed calendar “{event.source_name}”. Edit it in its own calendar app; changes appear here after the next sync.</div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

function EventFormBody({ event, slot, onClose }: { event: CalendarEvent | null; slot: { date: string; time: string } | null; onClose: () => void }) {
  const tz = useTz();
  const { create, update, remove } = useEventMutations();
  const { toast, confirm } = useFeedback();
  const [title, setTitle] = useState(event?.title ?? '');
  const [date, setDate] = useState(event ? dateOf(event.start_at, tz) : (slot?.date ?? ''));
  const [start, setStart] = useState(event && !event.all_day ? fmtTime(event.start_at, tz) : (slot?.time ?? '09:00'));
  const [end, setEnd] = useState(() => {
    if (event && !event.all_day) return fmtTime(event.end_at, tz);
    const [h, m] = (slot?.time ?? '09:00').split(':').map(Number);
    return `${String(Math.min(h + 1, 23)).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  });
  const [allDay, setAllDay] = useState(event?.all_day ?? false);
  const [location, setLocation] = useState(event?.location ?? '');
  const [description, setDescription] = useState(event?.description ?? '');
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return setError('Give the event a title');
    if (!date) return setError('Pick a date');
    const startAt = allDay ? zonedToUtc(date, '00:00', tz) : zonedToUtc(date, start, tz);
    const endAt = allDay ? zonedToUtc(addDays(date, 1), '00:00', tz) : zonedToUtc(date, end, tz);
    if (endAt < startAt) return setError('The event ends before it starts');
    const body = { title: title.trim(), start_at: startAt.toISOString(), end_at: endAt.toISOString(), all_day: allDay, location, description };
    try {
      if (event) await update.mutateAsync({ id: event.id, ...body });
      else await create.mutateAsync(body);
      toast({ title: event ? 'Event updated' : 'Event added', body: body.title });
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function del() {
    if (!event) return;
    const ok = await confirm({ title: 'Delete this event?', body: `“${event.title}” will be removed.`, confirmLabel: 'Delete', danger: true });
    if (!ok) return;
    try {
      await remove.mutateAsync(event.id);
      toast({ title: 'Event deleted' });
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <form className="dialog-body" onSubmit={submit} noValidate>
      <div className="form-grid">
        <label className="field span-2">
          <span>Title</span>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} autoFocus />
        </label>
        <label className="field">
          <span>Date</span>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className="field" style={{ justifyContent: 'flex-end' }}>
          <span>All day</span>
          <input type="checkbox" className="check" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
        </label>
        {!allDay && (
          <>
            <label className="field">
              <span>Starts</span>
              <input className="input" type="time" value={start} onChange={(e) => setStart(e.target.value)} />
            </label>
            <label className="field">
              <span>Ends</span>
              <input className="input" type="time" value={end} onChange={(e) => setEnd(e.target.value)} />
            </label>
          </>
        )}
        <label className="field span-2">
          <span>Location</span>
          <input className="input" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={300} />
        </label>
        <label className="field span-2">
          <span>Notes</span>
          <textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={5000} />
        </label>
      </div>
      <p className="muted" style={{ fontSize: '0.78rem', margin: '8px 0 0' }}>
        Times are in {tz}.
      </p>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        {event && (
          <button type="button" className="btn btn-danger" onClick={del} style={{ marginRight: 'auto' }}>
            Delete
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={create.isPending || update.isPending}>
          {event ? 'Save changes' : 'Add event'}
        </button>
      </div>
    </form>
  );
}
