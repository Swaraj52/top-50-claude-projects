import { describe, expect, it } from 'vitest';
import { parseQuickAdd } from './quickAdd';

// Wednesday 4 Nov 2026, 10:00 in Kolkata (04:30 UTC).
const NOW = new Date('2026-11-04T04:30:00Z');
const IST = 'Asia/Kolkata';

describe('parseQuickAdd', () => {
  it('defaults to an undated medium task', () => {
    const r = parseQuickAdd('Water the plants', IST, undefined, NOW);
    expect(r).toMatchObject({ kind: 'task', title: 'Water the plants', priority: 'medium', dueDate: null, error: null });
  });

  it('reads a due date and a priority token', () => {
    const r = parseQuickAdd('Send invoice friday !high', IST, undefined, NOW);
    expect(r).toMatchObject({ kind: 'task', title: 'Send invoice', priority: 'high', dueDate: '2026-11-06' });
    expect(r.when).toBe('friday');
  });

  it('turns "remind me to" into a reminder at the given local time', () => {
    const r = parseQuickAdd('remind me to call mom tomorrow at 6pm', IST, undefined, NOW);
    expect(r.kind).toBe('reminder');
    expect(r.title).toBe('call mom');
    expect(r.start).toBe('2026-11-05T12:30:00.000Z'); // 18:00 IST
    expect(r.error).toBeNull();
  });

  it('defaults a date-only reminder to 09:00', () => {
    const r = parseQuickAdd('remind me to renew passport on friday', IST, undefined, NOW);
    expect(r.start).toBe('2026-11-06T03:30:00.000Z');
  });

  it('flags reminders without a time and reminders in the past', () => {
    expect(parseQuickAdd('remind me to stretch', IST, undefined, NOW).error).toMatch(/Say when/);
    expect(parseQuickAdd('remind me to stretch today at 8am', IST, undefined, NOW).error).toMatch(/passed/);
  });

  it('parses an event with a time range', () => {
    const r = parseQuickAdd('event Design review thursday 2-3:30pm', IST, undefined, NOW);
    expect(r).toMatchObject({ kind: 'event', title: 'Design review', allDay: false });
    expect(r.start).toBe('2026-11-05T08:30:00.000Z');
    expect(r.end).toBe('2026-11-05T10:00:00.000Z');
  });

  it('gives a timed event one hour when no end is given', () => {
    const r = parseQuickAdd('meeting Standup tomorrow 9:30am', IST, undefined, NOW);
    expect(r.start).toBe('2026-11-05T04:00:00.000Z');
    expect(r.end).toBe('2026-11-05T05:00:00.000Z');
  });

  it('makes a date-only event all-day in the user timezone', () => {
    const r = parseQuickAdd('event Offsite next monday', IST, undefined, NOW);
    expect(r.allDay).toBe(true);
    expect(r.start).toBe('2026-11-08T18:30:00.000Z'); // Mon 9 Nov 00:00 IST
    expect(r.end).toBe('2026-11-09T18:30:00.000Z');
  });

  it('lets the UI force a kind', () => {
    const r = parseQuickAdd('Dentist tomorrow 4pm', IST, 'event', NOW);
    expect(r.kind).toBe('event');
    expect(r.title).toBe('Dentist');
  });

  it('uses the profile timezone, not the browser one', () => {
    // At NOW it is still Tue 3 Nov 23:30 in New York, so "tomorrow" is 4 Nov there.
    const r = parseQuickAdd('remind me to join call tomorrow 9am', 'America/New_York', undefined, NOW);
    expect(r.start).toBe('2026-11-04T14:00:00.000Z'); // 09:00 EST (UTC-5)
  });

  it('requires a title', () => {
    expect(parseQuickAdd('tomorrow 5pm', IST, undefined, NOW).error).toBe('Add a title');
  });
});
