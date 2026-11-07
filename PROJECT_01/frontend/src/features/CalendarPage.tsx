import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { useEvents, useTz } from '../api/hooks';
import type { CalendarEvent } from '../api/types';
import { EventForm } from '../components/EventForm';
import { ErrorNotice } from '../components/ui';
import { addDays, dateOf, fmtShortDate, fmtTime, todayIn, wallTime, weekStart, zonedToUtc } from '../lib/dates';

const HOUR_PX = 48;

interface Placed {
  event: CalendarEvent;
  top: number;
  height: number;
  lane: number;
  lanes: number;
}

function layoutDay(events: CalendarEvent[], dayStart: number, dayEnd: number): Placed[] {
  const sorted = [...events].sort((a, b) => a.start_at.localeCompare(b.start_at));
  const laneEnds: number[] = [];
  const placed = sorted.map((event) => {
    const s = Math.max(new Date(event.start_at).getTime(), dayStart);
    const e = Math.min(new Date(event.end_at).getTime(), dayEnd);
    let lane = laneEnds.findIndex((end) => end <= s);
    if (lane === -1) lane = laneEnds.push(e) - 1;
    else laneEnds[lane] = e;
    const top = ((s - dayStart) / 3_600_000) * HOUR_PX;
    const height = Math.max(20, ((e - s) / 3_600_000) * HOUR_PX - 2);
    return { event, top, height, lane, lanes: 1 };
  });
  return placed.map((p) => ({ ...p, lanes: Math.max(1, laneEnds.length) }));
}

export function CalendarPage() {
  const tz = useTz();
  const today = todayIn(tz);
  const [monday, setMonday] = useState(() => weekStart(today));
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(monday, i)), [monday]);
  const start = zonedToUtc(monday, '00:00', tz).toISOString();
  const end = zonedToUtc(addDays(monday, 7), '00:00', tz).toISOString();
  const { data, error, isLoading, refetch } = useEvents(start, end);
  const [open, setOpen] = useState<CalendarEvent | null | { date: string; time: string }>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = 7 * HOUR_PX - 16;
  }, []);
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(t);
  }, []);

  const byDay = useMemo(() => {
    const map = new Map<string, { allDay: CalendarEvent[]; timed: Placed[] }>();
    for (const day of days) {
      const ds = zonedToUtc(day, '00:00', tz).getTime();
      const de = zonedToUtc(addDays(day, 1), '00:00', tz).getTime();
      const overlapping = (data ?? []).filter((e) => new Date(e.start_at).getTime() < de && new Date(e.end_at).getTime() > ds);
      map.set(day, {
        allDay: overlapping.filter((e) => e.all_day),
        timed: layoutDay(overlapping.filter((e) => !e.all_day), ds, de),
      });
    }
    return map;
  }, [data, days, tz]);

  function clickSlot(day: string, e: MouseEvent<HTMLDivElement>) {
    if (e.target !== e.currentTarget) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const minutes = Math.floor(((e.clientY - rect.top) / HOUR_PX) * 2) * 30;
    const h = Math.min(23, Math.floor(minutes / 60));
    setOpen({ date: day, time: `${String(h).padStart(2, '0')}:${minutes % 60 === 0 ? '00' : '30'}` });
  }

  const nowWall = wallTime(new Date(now), tz);
  const nowTop = (nowWall.hour + nowWall.minute / 60) * HOUR_PX;
  const label = `${fmtShortDate(days[0])} – ${fmtShortDate(days[6])} ${days[6].slice(0, 4)}`;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="kicker">Schedule</div>
          <h1>Week of {fmtShortDate(monday).replace(/^\w+ /, '')}</h1>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button className="btn btn-sm" onClick={() => setMonday(addDays(monday, -7))} aria-label="Previous week">
            ←
          </button>
          <button className="btn btn-sm" onClick={() => setMonday(weekStart(today))}>
            This week
          </button>
          <button className="btn btn-sm" onClick={() => setMonday(addDays(monday, 7))} aria-label="Next week">
            →
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => setOpen({ date: today, time: '09:00' })}>
            New event
          </button>
        </div>
      </header>
      <p className="muted mono" style={{ fontSize: '0.75rem', marginTop: -12 }}>
        {label} · {tz} {isLoading && '· loading…'}
      </p>
      {error && <ErrorNotice error={error} retry={() => refetch()} />}

      <div className="week" aria-label={`Week ${label}`} ref={scroller} style={{ maxHeight: '70vh', overflow: 'auto' }}>
        <div className="week-grid" style={{ position: 'sticky', top: 0, zIndex: 3, background: 'var(--card)' }}>
          <div className="week-dayhead" style={{ borderLeft: 0 }} />
          {days.map((day) => (
            <div key={day} className={`week-dayhead ${day === today ? 'today' : ''}`}>
              {fmtShortDate(day).split(' ')[0]}
              <span className="num">{Number(day.slice(8))}</span>
            </div>
          ))}
          <div className="week-allday mono" style={{ borderLeft: 0, fontSize: '0.62rem', color: 'var(--muted)' }}>
            ALL DAY
          </div>
          {days.map((day) => (
            <div key={day} className="week-allday">
              {byDay.get(day)!.allDay.map((e) => (
                <button key={e.id} className="week-event allday" style={{ background: e.color }} onClick={() => setOpen(e)}>
                  {e.title}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div>
          <div className="week-grid" style={{ height: 24 * HOUR_PX }}>
            <div className="week-hours">
              {Array.from({ length: 23 }, (_, i) => (
                <span key={i} style={{ top: (i + 1) * HOUR_PX }}>
                  {String(i + 1).padStart(2, '0')}:00
                </span>
              ))}
            </div>
            {days.map((day) => (
              <div
                key={day}
                className={`week-col ${day === today ? 'today' : ''}`}
                onClick={(e) => clickSlot(day, e)}
                aria-label={`${fmtShortDate(day)}: click an empty slot to add an event`}
              >
                {day === today && <div className="week-now" style={{ top: nowTop }} aria-hidden />}
                {byDay.get(day)!.timed.map(({ event: e, top, height, lane, lanes }) => (
                  <button
                    key={e.id}
                    className={`week-event ${height < 38 ? 'compact' : ''}`}
                    style={{
                      top,
                      height,
                      background: e.color,
                      left: `calc(${(lane / lanes) * 100}% + 3px)`,
                      width: `calc(${100 / lanes}% - 6px)`,
                      right: 'auto',
                    }}
                    onClick={() => setOpen(e)}
                    title={`${e.title} · ${fmtTime(e.start_at, tz)}–${fmtTime(e.end_at, tz)}`}
                  >
                    <span className="t">
                      {dateOf(e.start_at, tz) === day ? fmtTime(e.start_at, tz) : '…'}
                    </span>
                    {e.title}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      <EventForm
        open={open !== null}
        onClose={() => setOpen(null)}
        event={open && 'id' in open ? open : null}
        slot={open && !('id' in open) ? open : null}
      />
    </>
  );
}
