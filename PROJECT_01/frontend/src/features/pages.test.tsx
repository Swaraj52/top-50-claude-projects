import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Dashboard } from '../api/types';
import { App } from '../App';
import { CommandBar } from '../components/CommandBar';
import { todayIn } from '../lib/dates';
import { ME, mockApi, renderApp } from '../test/utils';

const TODAY = todayIn('Asia/Kolkata');

function dashboard(over: Partial<Dashboard> = {}): Dashboard {
  return {
    date: TODAY,
    timezone: 'Asia/Kolkata',
    user_name: 'Ana',
    events: [],
    tasks: [
      { id: 7, title: 'Send proposal', notes: '', priority: 'high', status: 'todo', due_date: TODAY, completed_at: null, created_at: '2026-11-01T00:00:00Z' },
    ],
    reminders: [],
    priorities: [],
    emails: [],
    email_connected: false,
    calendars_connected: 0,
    counts: { overdue: 0, due_today: 1, done_today: 0, upcoming: 2, events_today: 0, unread_emails: 0, attention_emails: 0 },
    briefing: null,
    ...over,
  };
}

const RULE_BRIEFING = {
  id: 3,
  day: TODAY,
  source: 'rule' as const,
  model: null,
  note: null,
  content: {
    headline: '1 due',
    summary: 'Your calendar has no timed events today. 1 task is due today.',
    schedule_notes: ['Longest free block: 08:00-18:00 (10h 0m).'],
    focus: [{ title: 'Send proposal', reason: 'High priority, due today', task_id: 7 }],
    heads_up: [],
  },
  created_at: new Date().toISOString(),
};

describe('signed-out app', () => {
  it('validates registration before calling the API', async () => {
    const calls = mockApi({
      'GET /auth/me': () => new Response(JSON.stringify({ detail: 'Not signed in' }), { status: 401 }),
      'POST /auth/register': (c) => ({ ...ME, name: (c.body as { name: string }).name }),
      'GET /dashboard/today': () => dashboard(),
      'GET /meta': () => ({ version: '1.0.0', ai_enabled: false, ai_model: null }),
      'GET /reminders/due': () => [],
    });
    renderApp(<App />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Create an account' }));
    await user.type(screen.getByLabelText('Name'), 'Ana');
    await user.type(screen.getByLabelText('Email'), 'ana@example.com');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters');
    expect(calls.some((c) => c.path === '/auth/register')).toBe(false);

    await user.type(screen.getByLabelText('Password'), '-but-longer');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    await waitFor(() => expect(calls.find((c) => c.path === '/auth/register')?.body).toMatchObject({ email: 'ana@example.com', name: 'Ana' }));
    // The app must actually switch to the signed-in view.
    expect(await screen.findByText('No briefing yet today')).toBeInTheDocument();
  });

  it('signs in, then signs out back to the login form', async () => {
    let signedIn = false;
    mockApi({
      'GET /auth/me': () => (signedIn ? ME : new Response(JSON.stringify({ detail: 'Not signed in' }), { status: 401 })),
      'POST /auth/login': () => {
        signedIn = true;
        return ME;
      },
      'POST /auth/logout': () => {
        signedIn = false;
        return undefined;
      },
      'GET /dashboard/today': () => dashboard(),
      'GET /meta': () => ({ version: '1.0.0', ai_enabled: false, ai_model: null }),
      'GET /reminders/due': () => [],
    });
    renderApp(<App />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Email'), 'ana@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct horse 1');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Send proposal')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});

describe('Today page', () => {
  function signedIn(dash: Dashboard, extra = {}) {
    return mockApi({
      'GET /auth/me': () => ME,
      'GET /meta': () => ({ version: '1.0.0', ai_enabled: false, ai_model: null }),
      'GET /dashboard/today': () => dash,
      'GET /reminders/due': () => [],
      ...extra,
    });
  }

  it('shows the masthead, due tasks and an empty briefing with honest AI status', async () => {
    signedIn(dashboard());
    renderApp(<App />);
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/\w+day,? \d+ \w+/);
    expect(screen.getByText('Send proposal')).toBeInTheDocument();
    expect(screen.getByText('No briefing yet today')).toBeInTheDocument();
    expect(screen.getByText(/Add an ANTHROPIC_API_KEY/)).toBeInTheDocument();
    expect(screen.getByText('No mailbox connected')).toBeInTheDocument();
  });

  it('labels a rule-based briefing and offers its suggestions as priorities', async () => {
    const calls = signedIn(dashboard({ briefing: RULE_BRIEFING }), { 'PUT /priorities': (c: { body: unknown }) => (c.body as { items: unknown[] }).items });
    renderApp(<App />);
    expect(await screen.findByText('Rule-based summary')).toBeInTheDocument();
    expect(screen.queryByText(/Written by Claude/)).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Use the briefing’s suggestions' }));
    expect(screen.getByLabelText('Priority 1')).toHaveValue('Send proposal');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
        day: TODAY,
        items: [{ text: 'Send proposal', task_id: 7, done: false }],
      }),
    );
  });

  it('labels an AI briefing with the model that wrote it', async () => {
    signedIn(dashboard({ briefing: { ...RULE_BRIEFING, source: 'ai', model: 'claude-opus-5-5' } }));
    renderApp(<App />);
    expect(await screen.findByText(/Written by Claude · claude-opus-5-5/)).toBeInTheDocument();
  });

  it('completes a task from the due list', async () => {
    const calls = signedIn(dashboard(), { 'PATCH /tasks/7': () => ({}) });
    renderApp(<App />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('checkbox', { name: 'Complete “Send proposal”' }));
    await waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ status: 'done' }));
    expect(await screen.findByText('Done')).toBeInTheDocument();
  });
});

describe('Command bar', () => {
  it('previews and creates a reminder from natural language', async () => {
    const calls = mockApi({ 'GET /auth/me': () => ME, 'POST /reminders': () => ({ id: 1 }) });
    renderApp(<CommandBar open onClose={() => {}} />);
    const user = userEvent.setup();
    const input = await screen.findByLabelText('Quick add a task, reminder or event');
    await waitFor(() => expect(calls.some((c) => c.path === '/auth/me')).toBe(true));
    await user.type(input, 'remind me to call mom tomorrow at 6pm');
    const preview = screen.getByText('Type').closest('dl')!;
    expect(within(preview).getByText('reminder')).toBeInTheDocument();
    expect(within(preview).getByText('call mom')).toBeInTheDocument();
    expect(within(preview).getByText(/18:00/)).toBeInTheDocument();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(calls.find((c) => c.path === '/reminders')?.body).toMatchObject({ text: 'call mom' }));
  });

  it('refuses to submit an invalid entry', async () => {
    const calls = mockApi({ 'GET /auth/me': () => ME });
    renderApp(<CommandBar open onClose={() => {}} />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Quick add a task, reminder or event'), 'remind me to stretch');
    expect(screen.getByRole('alert')).toHaveTextContent('Say when');
    await user.keyboard('{Enter}');
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });
});
