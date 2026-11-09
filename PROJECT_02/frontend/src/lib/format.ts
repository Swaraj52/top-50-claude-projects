import type { Kind } from '../api/types';

export const KIND_LABEL: Record<Kind, string> = {
  article: 'Article',
  video: 'Video',
  newsletter: 'Newsletter',
  note: 'Note',
  pdf: 'PDF',
};

const KIND_CODE: Record<Kind, string> = { article: 'ART', video: 'VID', newsletter: 'NWS', note: 'NTE', pdf: 'PDF' };

/** A library-style call number, e.g. "ART 0042". */
export function callNumber(kind: Kind, id: number): string {
  return `${KIND_CODE[kind]} ${String(id).padStart(4, '0')}`;
}

export function timeAgo(iso: string, now = new Date()): string {
  const secs = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso));
}

export function hostOf(url: string | null): string {
  if (!url) return '';
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

export const HL_START = '';
export const HL_END = '';

/** Split an FTS snippet into plain and highlighted runs (never parsed as HTML). */
export function splitHighlights(snippet: string): { text: string; hit: boolean }[] {
  const parts: { text: string; hit: boolean }[] = [];
  let rest = snippet;
  while (rest.length) {
    const start = rest.indexOf(HL_START);
    if (start === -1) {
      parts.push({ text: rest, hit: false });
      break;
    }
    if (start > 0) parts.push({ text: rest.slice(0, start), hit: false });
    const end = rest.indexOf(HL_END, start + 1);
    if (end === -1) {
      parts.push({ text: rest.slice(start + 1), hit: true });
      break;
    }
    parts.push({ text: rest.slice(start + 1, end), hit: true });
    rest = rest.slice(end + 1);
  }
  return parts.filter((p) => p.text.length > 0);
}

/** Split an answer into text and [S#] citation markers. */
export function splitCitations(answer: string): (string | number)[] {
  const out: (string | number)[] = [];
  let last = 0;
  for (const m of answer.matchAll(/\[S(\d+)\]/g)) {
    if (m.index! > last) out.push(answer.slice(last, m.index));
    out.push(Number(m[1]));
    last = m.index! + m[0].length;
  }
  if (last < answer.length) out.push(answer.slice(last));
  return out;
}

export function looksLikeUrl(text: string): boolean {
  const t = text.trim();
  return /^(https?:\/\/)?[\w-]+(\.[\w-]+)+(\/\S*)?$/i.test(t) && !/\s/.test(t);
}

export function parseTags(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((t) => t.trim())
    .filter(Boolean);
}
