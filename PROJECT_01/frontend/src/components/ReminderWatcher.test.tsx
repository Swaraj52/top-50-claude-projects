import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useQueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { mockApi, renderApp } from '../test/utils';
import { ReminderWatcher } from './ReminderWatcher';

const due = { id: 4, text: 'Call the bank', remind_at: '2026-11-07T10:00:00Z', status: 'pending', task_id: null };

function Refetch() {
  const qc = useQueryClient();
  return <button onClick={() => qc.invalidateQueries({ queryKey: ['reminders'] })}>refetch</button>;
}

describe('ReminderWatcher', () => {
  it('raises a sticky toast for a due reminder and snoozes it', async () => {
    let list = [due];
    const calls = mockApi({
      'GET /reminders/due': () => list,
      'POST /reminders/4/snooze': () => {
        list = [];
        return { ...due, remind_at: '2026-11-07T10:10:00Z' };
      },
    });
    renderApp(<ReminderWatcher />);
    expect(await screen.findByText('Call the bank')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Snooze 10 min' }));
    await waitFor(() => expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ minutes: 10 }));
    await waitFor(() => expect(screen.queryByText('Call the bank')).not.toBeInTheDocument());
  });

  it('removes the toast when the reminder is handled somewhere else', async () => {
    let list = [due];
    mockApi({ 'GET /reminders/due': () => list });
    renderApp(
      <>
        <ReminderWatcher />
        <Refetch />
      </>,
    );
    expect(await screen.findByText('Call the bank')).toBeInTheDocument();
    list = []; // dismissed from the dashboard card
    await userEvent.setup().click(screen.getByRole('button', { name: 'refetch' }));
    await waitFor(() => expect(screen.queryByText('Call the bank')).not.toBeInTheDocument());
  });
});
