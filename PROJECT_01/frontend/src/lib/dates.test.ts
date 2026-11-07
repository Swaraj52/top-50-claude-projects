import { describe, expect, it } from 'vitest';
import { addDays, daysBetween, dueLabel, fmtTime, todayIn, tzOffsetMinutes, weekStart, zonedToUtc } from './dates';

describe('dates', () => {
  it('computes offsets including DST', () => {
    expect(tzOffsetMinutes(new Date('2026-01-15T12:00:00Z'), 'Asia/Kolkata')).toBe(330);
    expect(tzOffsetMinutes(new Date('2026-07-15T12:00:00Z'), 'Europe/London')).toBe(60);
    expect(tzOffsetMinutes(new Date('2026-01-15T12:00:00Z'), 'Europe/London')).toBe(0);
  });

  it('converts wall time to UTC across a DST change', () => {
    expect(zonedToUtc('2026-03-29', '12:00', 'Europe/London').toISOString()).toBe('2026-03-29T11:00:00.000Z');
    expect(zonedToUtc('2026-03-28', '12:00', 'Europe/London').toISOString()).toBe('2026-03-28T12:00:00.000Z');
  });

  it('knows today in a given zone', () => {
    const lateUtc = new Date('2026-11-04T20:00:00Z'); // already 5 Nov in Kolkata
    expect(todayIn('Asia/Kolkata', lateUtc)).toBe('2026-11-05');
    expect(todayIn('UTC', lateUtc)).toBe('2026-11-04');
  });

  it('does day arithmetic across month and year ends', () => {
    expect(daysBetween('2026-01-31', '2026-02-01')).toBe(1);
    expect(daysBetween('2026-12-31', '2027-01-01')).toBe(1);
    expect(addDays('2026-02-28', 1)).toBe('2026-03-01');
    expect(weekStart('2026-11-08')).toBe('2026-11-02'); // Sunday -> Monday
    expect(weekStart('2026-11-02')).toBe('2026-11-02');
  });

  it('labels due dates', () => {
    expect(dueLabel('2026-11-03', '2026-11-04')).toEqual({ text: 'Yesterday', tone: 'overdue' });
    expect(dueLabel('2026-11-01', '2026-11-04')).toEqual({ text: '3 days overdue', tone: 'overdue' });
    expect(dueLabel('2026-11-04', '2026-11-04').tone).toBe('today');
    expect(dueLabel('2026-11-05', '2026-11-04').text).toBe('Tomorrow');
    expect(dueLabel(null, '2026-11-04').tone).toBe('none');
  });

  it('formats times in the user zone', () => {
    expect(fmtTime('2026-11-04T04:30:00Z', 'Asia/Kolkata')).toBe('10:00');
  });
});
