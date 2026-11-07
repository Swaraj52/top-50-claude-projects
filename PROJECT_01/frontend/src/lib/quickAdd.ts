/**
 * Natural-language quick add, e.g.
 *   "Send invoice friday !high"           -> task due Friday, high priority
 *   "remind me to call mom tomorrow 6pm"  -> reminder at 18:00 tomorrow
 *   "event Design review thu 2-3pm"       -> event 14:00-15:00 Thursday
 * Dates are read in the user's profile timezone, not the browser's.
 */
import * as chrono from 'chrono-node';
import { addDays, isoDate, tzOffsetMinutes, zonedToUtc } from './dates';
import type { Priority } from '../api/types';

export type QuickKind = 'task' | 'reminder' | 'event';

export interface QuickParse {
  kind: QuickKind;
  title: string;
  priority: Priority;
  /** task: due date (YYYY-MM-DD) or null */
  dueDate: string | null;
  /** reminder / event: start instant (ISO, UTC) */
  start: string | null;
  /** event: end instant (ISO, UTC) */
  end: string | null;
  allDay: boolean;
  /** what was recognised as the date/time, for the preview */
  when: string | null;
  error: string | null;
}

const KIND_PREFIX: [RegExp, QuickKind][] = [
  [/^(remind\s+me\s+(to\s+)?|reminder:?\s+|r:\s*)/i, 'reminder'],
  [/^(event:?\s+|meeting:?\s+|e:\s*)/i, 'event'],
  [/^(task:?\s+|todo:?\s+|t:\s*)/i, 'task'],
];

const PRIORITY_TOKENS: [RegExp, Priority][] = [
  [/(^|\s)(!high|!h|!!!)(?=\s|$)/i, 'high'],
  [/(^|\s)(!low|!l)(?=\s|$)/i, 'low'],
  [/(^|\s)(!medium|!med|!m)(?=\s|$)/i, 'medium'],
];

const pad = (n: number) => String(n).padStart(2, '0');

function tidy(title: string): string {
  return title
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+(at|on|by|from|due|for)$/i, '')
    .replace(/^(at|on|by)\s+/i, '')
    .replace(/[\s,;:-]+$/, '')
    .trim();
}

export function parseQuickAdd(input: string, tz: string, forced?: QuickKind, now = new Date()): QuickParse {
  let text = input.trim();
  let kind: QuickKind = 'task';
  for (const [re, k] of KIND_PREFIX) {
    if (re.test(text)) {
      kind = k;
      text = text.replace(re, '');
      break;
    }
  }
  if (forced) kind = forced;

  let priority: Priority = 'medium';
  for (const [re, p] of PRIORITY_TOKENS) {
    if (re.test(text)) {
      priority = p;
      text = text.replace(re, ' ');
      break;
    }
  }

  const ref = { instant: now, timezone: tzOffsetMinutes(now, tz) };
  const [hit] = chrono.parse(text, ref, { forwardDate: true });

  const result: QuickParse = {
    kind,
    title: '',
    priority,
    dueDate: null,
    start: null,
    end: null,
    allDay: false,
    when: hit ? hit.text : null,
    error: null,
  };

  if (hit) text = text.slice(0, hit.index) + ' ' + text.slice(hit.index + hit.text.length);
  result.title = tidy(text);

  if (!result.title) {
    result.error = 'Add a title';
    return result;
  }

  if (!hit) {
    if (kind === 'task') return result;
    result.error = kind === 'reminder' ? 'Say when, e.g. "tomorrow 9am" or "in 2 hours"' : 'Say when, e.g. "fri 2-3pm"';
    return result;
  }

  const s = hit.start;
  const date = isoDate({ year: s.get('year')!, month: s.get('month')!, day: s.get('day')! });
  const hasTime = s.isCertain('hour');

  if (kind === 'task') {
    result.dueDate = date;
    return result;
  }

  if (kind === 'reminder') {
    const time = hasTime ? `${pad(s.get('hour')!)}:${pad(s.get('minute') ?? 0)}` : '09:00';
    const at = zonedToUtc(date, time, tz);
    if (at.getTime() < now.getTime() - 60_000) {
      result.error = 'That time has already passed';
    }
    result.start = at.toISOString();
    return result;
  }

  // event
  if (!hasTime) {
    result.allDay = true;
    const endDate = hit.end ? isoDate({ year: hit.end.get('year')!, month: hit.end.get('month')!, day: hit.end.get('day')! }) : date;
    result.start = zonedToUtc(date, '00:00', tz).toISOString();
    result.end = zonedToUtc(addDays(endDate, 1), '00:00', tz).toISOString();
    return result;
  }
  const start = zonedToUtc(date, `${pad(s.get('hour')!)}:${pad(s.get('minute') ?? 0)}`, tz);
  let end = new Date(start.getTime() + 60 * 60_000);
  if (hit.end && hit.end.isCertain('hour')) {
    const e = hit.end;
    const endDay = isoDate({ year: e.get('year')!, month: e.get('month')!, day: e.get('day')! });
    end = zonedToUtc(endDay, `${pad(e.get('hour')!)}:${pad(e.get('minute') ?? 0)}`, tz);
    if (end <= start) end = new Date(start.getTime() + 60 * 60_000);
  }
  result.start = start.toISOString();
  result.end = end.toISOString();
  return result;
}
