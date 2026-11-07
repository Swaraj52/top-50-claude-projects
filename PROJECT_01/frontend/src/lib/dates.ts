/**
 * Timezone-aware date helpers. The user's profile timezone (not the browser's) decides
 * what "today" means, so every helper takes an IANA zone explicitly.
 */

const partsCache = new Map<string, Intl.DateTimeFormat>();

function partsFormatter(tz: string): Intl.DateTimeFormat {
  let f = partsCache.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    partsCache.set(tz, f);
  }
  return f;
}

export interface WallTime {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
  second: number;
}

export function wallTime(instant: Date, tz: string): WallTime {
  const parts = Object.fromEntries(
    partsFormatter(tz)
      .formatToParts(instant)
      .filter((p) => p.type !== 'literal')
      .map((p) => [p.type, Number(p.value)]),
  );
  return {
    year: parts.year,
    month: parts.month,
    day: parts.day,
    hour: parts.hour % 24,
    minute: parts.minute,
    second: parts.second,
  };
}

/** Offset of `tz` from UTC at `instant`, in minutes (e.g. +330 for Asia/Kolkata). */
export function tzOffsetMinutes(instant: Date, tz: string): number {
  const w = wallTime(instant, tz);
  const asUtc = Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute, w.second);
  return Math.round((asUtc - Math.floor(instant.getTime() / 1000) * 1000) / 60_000);
}

/** The UTC instant of a wall-clock time in `tz` (handles DST by re-checking the offset). */
export function zonedToUtc(date: string, time: string, tz: string): Date {
  const [y, m, d] = date.split('-').map(Number);
  const [hh, mm] = time.split(':').map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  let instant = new Date(guess - tzOffsetMinutes(new Date(guess), tz) * 60_000);
  const corrected = new Date(guess - tzOffsetMinutes(instant, tz) * 60_000);
  if (corrected.getTime() !== instant.getTime()) instant = corrected;
  return instant;
}

const pad = (n: number) => String(n).padStart(2, '0');

export function isoDate(w: Pick<WallTime, 'year' | 'month' | 'day'>): string {
  return `${w.year}-${pad(w.month)}-${pad(w.day)}`;
}

export function todayIn(tz: string, now = new Date()): string {
  return isoDate(wallTime(now, tz));
}

export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}

function utcMidnight(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((utcMidnight(to) - utcMidnight(from)) / 86_400_000);
}

/** Monday of the week containing `date`. */
export function weekStart(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0 = Sunday
  return addDays(date, -((dow + 6) % 7));
}

export function fmtTime(iso: string, tz: string): string {
  const w = wallTime(new Date(iso), tz);
  return `${pad(w.hour)}:${pad(w.minute)}`;
}

export function dateOf(iso: string, tz: string): string {
  return isoDate(wallTime(new Date(iso), tz));
}

/** "Saturday, 7 November" for a YYYY-MM-DD date. */
export function fmtLongDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

/** "Sat 7 Nov" */
export function fmtShortDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

export function dueLabel(due: string | null, today: string): { text: string; tone: 'overdue' | 'today' | 'soon' | 'later' | 'none' } {
  if (!due) return { text: 'No date', tone: 'none' };
  const diff = daysBetween(today, due);
  if (diff < 0) return { text: diff === -1 ? 'Yesterday' : `${-diff} days overdue`, tone: 'overdue' };
  if (diff === 0) return { text: 'Today', tone: 'today' };
  if (diff === 1) return { text: 'Tomorrow', tone: 'soon' };
  if (diff < 7) return { text: fmtShortDate(due).split(' ')[0], tone: 'soon' };
  return { text: fmtShortDate(due), tone: 'later' };
}

export function relativeFromNow(iso: string, now = new Date()): string {
  const mins = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000);
  const abs = Math.abs(mins);
  const unit = abs < 60 ? `${abs} min` : abs < 1440 ? `${Math.round(abs / 60)} h` : `${Math.round(abs / 1440)} d`;
  if (abs < 1) return 'now';
  return mins > 0 ? `in ${unit}` : `${unit} ago`;
}

export function greeting(tz: string, now = new Date()): string {
  const h = wallTime(now, tz).hour;
  return h < 5 ? 'Up late' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export const browserTimezone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

export function supportedTimezones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  return intl.supportedValuesOf ? intl.supportedValuesOf('timeZone') : ['UTC'];
}
