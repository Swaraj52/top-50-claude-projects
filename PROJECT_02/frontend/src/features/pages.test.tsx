import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Answer, ItemCard, ItemDetail } from '../api/types';
import { App } from '../App';
import { HL_END, HL_START } from '../lib/format';
import { ME, mockApi, renderApp } from '../test/utils';
import { AnswerView } from './AskPage';

const CARD: ItemCard = {
  id: 42,
  kind: 'article',
  status: 'inbox',
  favorite: false,
  title: 'Why sleep matters for memory',
  url: 'https://brainweekly.example/sleep',
  source_name: 'Brain Weekly',
  author: 'Maya Rao',
  word_count: 900,
  reading_minutes: 4,
  has_transcript: false,
  thumbnail_url: null,
  tags: ['sleep'],
  tldr: 'Deep sleep consolidates memory.',
  created_at: new Date().toISOString(),
};

const DETAIL: ItemDetail = { ...CARD, description: '', content: 'Para one.\n\nPara two.', published: '', summary: null, updated_at: CARD.created_at };
const STATS = { inbox: 1, library: 3, archived: 0, favorites: 0, by_kind: { article: 4 }, tags: 2, questions: 0 };
const META = { version: '1.0.0', ai_enabled: false, ai_model: null };

function signedIn(extra: Record<string, (c: { body: unknown }) => unknown> = {}) {
  return mockApi({
    'GET /auth/me': () => ME,
    'GET /meta': () => META,
    'GET /items/stats': () => STATS,
    'GET /items': () => ({ items: [CARD], total: 1 }),
    'GET /tags': () => [{ id: 1, name: 'sleep', count: 1 }],
    'GET /ask/history': () => [],
    ...extra,
  });
}

describe('Inbox', () => {
  it('validates the link before saving and saves with tags', async () => {
    const calls = signedIn({ 'POST /items/url': () => ({ item: { ...DETAIL, id: 43, title: 'Tiny habits' }, warnings: [] }) });
    renderApp(<App />);
    const user = userEvent.setup();
    const input = await screen.findByLabelText('Link to save');
    await user.type(input, 'not a link');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(screen.getByRole('alert')).toHaveTextContent('full web address');
    expect(calls.some((c) => c.method === 'POST')).toBe(false);

    await user.clear(input);
    await user.type(input, 'https://habits.example/tiny');
    await user.type(screen.getByLabelText('Tags'), 'habits, focus');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(calls.find((c) => c.path === '/items/url')?.body).toEqual({ url: 'https://habits.example/tiny', tags: ['habits', 'focus'] }));
    expect(await screen.findByText('Saved to inbox')).toBeInTheDocument();
    // Tags belong to that save only; they must not carry over to the next link.
    expect(screen.getByLabelText('Tags')).toHaveValue('');
  });

  it('prefills the link from the bookmarklet parameter', async () => {
    signedIn();
    renderApp(<App />, '/?add=https%3A%2F%2Fexample.com%2Fpost');
    expect(await screen.findByLabelText('Link to save')).toHaveValue('https://example.com/post');
  });

  it('files an inbox card into the library', async () => {
    const calls = signedIn({ 'PATCH /items/42': () => ({ ...DETAIL, status: 'library' }) });
    renderApp(<App />);
    const user = userEvent.setup();
    const card = await screen.findByRole('article', { name: CARD.title });
    expect(within(card).getByText('ART 0042')).toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Keep' }));
    await waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'library' }));
  });
});

describe('Search', () => {
  it('renders highlights as <mark> without injecting HTML', async () => {
    signedIn({
      'GET /search': () => ({
        query: 'sleep',
        mode: 'all',
        hits: [{ item: CARD, snippet: `deep ${HL_START}sleep${HL_END} <img src=x onerror=alert(1)>` }],
      }),
    });
    const { container } = renderApp(<App />, '/search?q=sleep');
    const mark = await screen.findByText('sleep', { selector: 'mark' });
    expect(mark.tagName).toBe('MARK');
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText(/onerror=alert/)).toBeInTheDocument();
  });
});

describe('Ask', () => {
  const answer: Answer = {
    id: 9,
    question: 'Does caffeine hurt sleep?',
    answer: 'Yes, a late coffee delays sleep [S1].',
    source: 'ai',
    model: 'claude-opus-5-5',
    note: null,
    confidence: 'high',
    citations: [{ n: 1, item_id: 42, title: CARD.title, url: CARD.url, excerpt: 'Caffeine blocks adenosine receptors…' }],
    created_at: new Date().toISOString(),
  };

  it('labels AI answers and links citations to items', () => {
    renderApp(<AnswerView answer={answer} />);
    expect(screen.getByText(/Answered by Claude · claude-opus-5-5/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Source 1' })).toHaveAttribute('href', '#source-9-1');
    expect(screen.getByRole('link', { name: CARD.title })).toHaveAttribute('href', '/items/42');
  });

  it('labels passage-only results honestly', () => {
    renderApp(<AnswerView answer={{ ...answer, source: 'passages', model: null, confidence: null, answer: 'No AI answer (Claude is not configured).' }} />);
    expect(screen.getByText('No AI answer · retrieved passages')).toBeInTheDocument();
    expect(screen.queryByText(/Answered by Claude/)).not.toBeInTheDocument();
  });

  it('asks within a tag', async () => {
    const calls = signedIn({ 'POST /ask': () => answer });
    renderApp(<App />, '/ask');
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Your question'), 'Does caffeine hurt sleep?');
    await screen.findByRole('option', { name: 'Tag: sleep' });
    await user.selectOptions(screen.getByLabelText('Limit to tag'), 'sleep');
    await user.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(calls.find((c) => c.path === '/ask')?.body).toEqual({ question: 'Does caffeine hurt sleep?', tag: 'sleep' }));
    expect(await screen.findByText(/a late coffee delays sleep/)).toBeInTheDocument();
  });
});

describe('Session', () => {
  it('signs in and out', async () => {
    let signedInNow = false;
    mockApi({
      'GET /auth/me': () => (signedInNow ? ME : new Response(JSON.stringify({ detail: 'Not signed in' }), { status: 401 })),
      'POST /auth/login': () => {
        signedInNow = true;
        return ME;
      },
      'POST /auth/logout': () => {
        signedInNow = false;
        return undefined;
      },
      'GET /meta': () => META,
      'GET /items/stats': () => STATS,
      'GET /items': () => ({ items: [], total: 0 }),
    });
    renderApp(<App />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Email'), 'rhea@example.com');
    await user.type(screen.getByLabelText('Password'), 'long enough 1');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Inbox zero')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});
