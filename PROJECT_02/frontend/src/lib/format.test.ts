import { describe, expect, it } from 'vitest';
import { callNumber, HL_END, HL_START, looksLikeUrl, parseTags, splitCitations, splitHighlights, timeAgo } from './format';

describe('format helpers', () => {
  it('splits FTS highlight markers into runs', () => {
    expect(splitHighlights(`a ${HL_START}sleep${HL_END} and ${HL_START}naps${HL_END}`)).toEqual([
      { text: 'a ', hit: false },
      { text: 'sleep', hit: true },
      { text: ' and ', hit: false },
      { text: 'naps', hit: true },
    ]);
    expect(splitHighlights('no marks <b>here</b>')).toEqual([{ text: 'no marks <b>here</b>', hit: false }]);
    expect(splitHighlights(`${HL_START}unterminated`)).toEqual([{ text: 'unterminated', hit: true }]);
  });

  it('splits citation markers', () => {
    expect(splitCitations('Naps help [S1] but coffee hurts [S2][S3].')).toEqual(['Naps help ', 1, ' but coffee hurts ', 2, 3, '.']);
  });

  it('formats call numbers and ages', () => {
    expect(callNumber('video', 7)).toBe('VID 0007');
    const now = new Date('2026-11-09T12:00:00Z');
    expect(timeAgo('2026-11-09T11:58:00Z', now)).toBe('2 min ago');
    expect(timeAgo('2026-11-07T12:00:00Z', now)).toBe('2 d ago');
  });

  it('recognises links and tags', () => {
    expect(looksLikeUrl('https://example.com/a?b=1')).toBe(true);
    expect(looksLikeUrl('example.com/post')).toBe(true);
    expect(looksLikeUrl('just some words')).toBe(false);
    expect(parseTags(' sleep, memory ,,\nfocus ')).toEqual(['sleep', 'memory', 'focus']);
  });
});
