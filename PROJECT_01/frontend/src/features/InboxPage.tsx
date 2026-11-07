import { useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useEmailAccount, useEmailMutations, useEmails, useTz } from '../api/hooks';
import { useFeedback } from '../components/feedback';
import { Empty, ErrorNotice, Skeleton } from '../components/ui';
import { dateOf, fmtShortDate, fmtTime, relativeFromNow, todayIn } from '../lib/dates';

type Filter = 'attention' | 'unread' | 'all';

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'attention', label: 'Needs attention' },
  { value: 'unread', label: 'Unread' },
  { value: 'all', label: 'Last 14 days' },
];

export function InboxPage() {
  const tz = useTz();
  const account = useEmailAccount();
  const [filter, setFilter] = useState<Filter>('attention');
  const messages = useEmails(filter, !!account.data);
  const { sync, makeTask } = useEmailMutations();
  const { toast } = useFeedback();
  const today = todayIn(tz);

  async function doSync() {
    try {
      const r = await sync.mutateAsync();
      toast({ title: 'Inbox synced', body: `${r.fetched} messages checked, ${r.attention} need attention` });
    } catch (err) {
      toast({ title: 'Email sync failed', body: errorMessage(err), tone: 'error' });
    }
  }

  if (account.isLoading) return <Skeleton lines={5} />;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="kicker">Email</div>
          <h1>Inbox</h1>
        </div>
        {account.data && (
          <button className="btn btn-primary" onClick={doSync} disabled={sync.isPending}>
            {sync.isPending ? 'Syncing…' : 'Sync now'}
          </button>
        )}
      </header>

      {!account.data ? (
        <Empty title="Connect a mailbox" action={<Link className="btn btn-sm" to="/settings">Go to Settings</Link>}>
          Daybook reads message headers over IMAP to show what needs a reply. It never sends, deletes or marks mail as read.
        </Empty>
      ) : (
        <div style={{ maxWidth: 860 }}>
          <p className="muted mono" style={{ fontSize: '0.75rem', marginTop: -10 }}>
            {account.data.username} · {account.data.mailbox} ·{' '}
            {account.data.last_synced_at ? `synced ${relativeFromNow(account.data.last_synced_at)}` : 'never synced'}
          </p>
          {account.data.last_error && <div className="notice error">Last sync failed: {account.data.last_error}</div>}
          <div className="tabs" role="tablist" aria-label="Email filters">
            {FILTERS.map((f) => (
              <button key={f.value} role="tab" className="tab" aria-selected={filter === f.value} onClick={() => setFilter(f.value)}>
                {f.label}
              </button>
            ))}
          </div>
          {messages.isLoading && <Skeleton lines={4} />}
          {messages.error && <ErrorNotice error={messages.error} retry={() => messages.refetch()} />}
          {messages.data?.length === 0 && (
            <Empty title={filter === 'attention' ? 'Nothing needs attention' : 'No messages'}>
              {account.data.last_synced_at ? 'Sync again later to pick up new mail.' : 'Run a first sync to load recent mail.'}
            </Empty>
          )}
          {messages.data?.map((m) => {
            const day = dateOf(m.received_at, tz);
            return (
              <div className="row" key={m.id}>
                {m.is_unread ? <span className="unread-dot" aria-label="Unread" /> : <span style={{ width: 7 }} />}
                <div className="row-main">
                  <div className="email-from">
                    {m.is_flagged && <span style={{ color: 'var(--accent)' }} title="Flagged">⚑ </span>}
                    {m.from_name} <span className="muted" style={{ fontWeight: 400, fontSize: '0.78rem' }}>{m.from_addr !== m.from_name ? m.from_addr : ''}</span>
                  </div>
                  <div className="row-title">{m.subject}</div>
                </div>
                <span className="mono muted" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                  {day === today ? fmtTime(m.received_at, tz) : fmtShortDate(day)}
                </span>
                {m.task_id ? (
                  <span className="chip">Task added</span>
                ) : (
                  <button
                    className="btn btn-sm"
                    onClick={() =>
                      makeTask.mutate(m.id, {
                        onSuccess: () => toast({ title: 'Task created', body: `Reply: ${m.subject}` }),
                        onError: (err) => toast({ title: 'Could not create task', body: errorMessage(err), tone: 'error' }),
                      })
                    }
                  >
                    Make task
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
