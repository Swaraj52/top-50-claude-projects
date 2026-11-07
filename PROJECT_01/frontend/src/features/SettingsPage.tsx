import { useState, type FormEvent } from 'react';
import { errorMessage } from '../api/client';
import {
  useCalendarMutations,
  useCalendars,
  useEmailAccount,
  useEmailMutations,
  useMe,
  useMeta,
  useUpdateProfile,
} from '../api/hooks';
import type { CalendarSource } from '../api/types';
import { useFeedback } from '../components/feedback';
import { Skeleton } from '../components/ui';
import { relativeFromNow, supportedTimezones } from '../lib/dates';

export function SettingsPage() {
  return (
    <>
      <header className="page-head">
        <div>
          <div className="kicker">Preferences &amp; connections</div>
          <h1>Settings</h1>
        </div>
      </header>
      <div className="settings-grid">
        <div>
          <CalendarsCard />
          <EmailCard />
        </div>
        <div>
          <ProfileCard />
          <AiCard />
          <NotificationsCard />
        </div>
      </div>
    </>
  );
}

// --- Profile ---------------------------------------------------------------------------

function ProfileCard() {
  const { data: me } = useMe();
  const update = useUpdateProfile();
  const { toast } = useFeedback();
  const [name, setName] = useState(me?.name ?? '');
  const [tz, setTz] = useState(me?.timezone ?? 'UTC');
  const zones = supportedTimezones();

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!zones.includes(tz) && tz !== 'UTC') {
      toast({ title: 'Unknown timezone', body: 'Pick one from the list, e.g. Europe/London.', tone: 'error' });
      return;
    }
    try {
      await update.mutateAsync({ name: name.trim(), timezone: tz });
      toast({ title: 'Profile saved' });
    } catch (err) {
      toast({ title: 'Could not save profile', body: errorMessage(err), tone: 'error' });
    }
  }

  return (
    <section className="card">
      <h2>Profile</h2>
      <p>{me?.email}</p>
      <form onSubmit={save} className="form-grid">
        <label className="field span-2">
          <span>Name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required />
        </label>
        <label className="field span-2">
          <span>Timezone</span>
          <input className="input" list="tz-list" value={tz} onChange={(e) => setTz(e.target.value)} />
          <datalist id="tz-list">
            {zones.map((z) => (
              <option key={z} value={z} />
            ))}
          </datalist>
        </label>
        <div className="span-2 form-actions" style={{ marginTop: 0 }}>
          <button className="btn btn-primary btn-sm" disabled={update.isPending || !name.trim()}>
            Save profile
          </button>
        </div>
      </form>
    </section>
  );
}

// --- Calendars -------------------------------------------------------------------------

const COLORS = ['#5b6cf0', '#e8833a', '#0f9d8a', '#c2411a', '#8e5bd6', '#2f80c2'];

function CalendarsCard() {
  const { data, isLoading } = useCalendars();
  const { subscribe, upload, sync, remove } = useCalendarMutations();
  const { toast, confirm } = useFeedback();
  const [mode, setMode] = useState<'url' | 'file'>('url');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [color, setColor] = useState(COLORS[0]);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (mode === 'url') {
        if (!name.trim() || !url.trim()) return setError('Give the calendar a name and its ICS address');
        const s = await subscribe.mutateAsync({ name: name.trim(), url: url.trim(), color });
        toast({ title: 'Calendar connected', body: `${s.name}: ${s.event_count} events` });
      } else {
        if (!file) return setError('Choose an .ics file');
        const form = new FormData();
        form.append('file', file);
        form.append('name', name.trim());
        form.append('color', color);
        const s = await upload.mutateAsync(form);
        toast({ title: 'Calendar imported', body: `${s.name}: ${s.event_count} events` });
      }
      setName('');
      setUrl('');
      setFile(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function del(s: CalendarSource) {
    const ok = await confirm({ title: `Remove “${s.name}”?`, body: `Its ${s.event_count} events will disappear from Daybook. Your original calendar is not touched.`, confirmLabel: 'Remove', danger: true });
    if (ok) remove.mutate(s.id, { onSuccess: () => toast({ title: 'Calendar removed' }) });
  }

  return (
    <section className="card">
      <h2>Calendars</h2>
      <p>Subscribe to an ICS feed or import an .ics file. Feeds are read-only and synced when you press Sync.</p>
      {isLoading && <Skeleton lines={2} />}
      {data?.map((s) => (
        <div className="row" key={s.id}>
          <span className="swatch" style={{ background: s.color }} />
          <div className="row-main">
            <div className="row-title">{s.name}</div>
            <div className="row-sub">
              <span>{s.kind === 'url' ? 'Feed' : 'Imported file'}</span>
              <span>· {s.event_count} events</span>
              {s.last_synced_at && <span>· synced {relativeFromNow(s.last_synced_at)}</span>}
            </div>
            {s.last_error && <div className="field-error">Last sync failed: {s.last_error}</div>}
          </div>
          {s.kind === 'url' && (
            <button
              className="btn btn-ghost btn-sm"
              disabled={sync.isPending}
              onClick={() =>
                sync.mutate(s.id, {
                  onSuccess: (r) => toast({ title: 'Calendar synced', body: `${r.event_count} events` }),
                  onError: (err) => toast({ title: 'Sync failed', body: errorMessage(err), tone: 'error' }),
                })
              }
            >
              Sync
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={() => del(s)}>
            Remove
          </button>
        </div>
      ))}

      <form onSubmit={add} style={{ marginTop: 16 }}>
        <div className="segmented" role="group" aria-label="How to add" style={{ marginBottom: 14 }}>
          <button type="button" aria-pressed={mode === 'url'} onClick={() => setMode('url')}>
            Subscribe by URL
          </button>
          <button type="button" aria-pressed={mode === 'file'} onClick={() => setMode('file')}>
            Upload .ics
          </button>
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder={mode === 'url' ? 'Work' : 'Defaults to file name'} maxLength={80} />
          </label>
          <div className="field">
            <span>Colour</span>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', minHeight: 40 }}>
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  aria-label={`Colour ${c}`}
                  aria-pressed={color === c}
                  onClick={() => setColor(c)}
                  style={{ width: 22, height: 22, borderRadius: 3, background: c, border: color === c ? '2px solid var(--ink)' : '2px solid transparent', cursor: 'pointer' }}
                />
              ))}
            </div>
          </div>
          {mode === 'url' ? (
            <label className="field span-2">
              <span>ICS address</span>
              <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://calendar.google.com/calendar/ical/…/basic.ics" inputMode="url" />
            </label>
          ) : (
            <label className="field span-2">
              <span>File</span>
              <input className="input" type="file" accept=".ics,text/calendar" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
          )}
        </div>
        {mode === 'url' && (
          <details style={{ fontSize: '0.82rem', marginTop: 10 }} className="muted">
            <summary>Where do I find this address?</summary>
            <p>
              <b>Google Calendar:</b> Settings → your calendar → Integrate calendar → “Secret address in iCal format”.
              <br />
              <b>Outlook:</b> Settings → Calendar → Shared calendars → Publish a calendar → ICS link.
              <br />
              <b>Apple iCloud:</b> share the calendar as a public calendar and copy the webcal:// link.
            </p>
            <p>The address is stored encrypted and never shown again.</p>
          </details>
        )}
        {error && (
          <div className="notice error" role="alert" style={{ marginTop: 12 }}>
            {error}
          </div>
        )}
        <div className="form-actions">
          <button className="btn btn-primary btn-sm" disabled={subscribe.isPending || upload.isPending}>
            {subscribe.isPending || upload.isPending ? 'Loading calendar…' : mode === 'url' ? 'Subscribe' : 'Import'}
          </button>
        </div>
      </form>
    </section>
  );
}

// --- Email -----------------------------------------------------------------------------

const PRESETS = [
  { label: 'Gmail', host: 'imap.gmail.com' },
  { label: 'Outlook', host: 'outlook.office365.com' },
  { label: 'iCloud', host: 'imap.mail.me.com' },
  { label: 'Yahoo', host: 'imap.mail.yahoo.com' },
];

function EmailCard() {
  const { data: account, isLoading } = useEmailAccount();
  const { connect, disconnect, sync } = useEmailMutations();
  const { toast, confirm } = useFeedback();
  const [editing, setEditing] = useState(false);
  const [host, setHost] = useState('');
  const [port, setPort] = useState(993);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mailbox, setMailbox] = useState('INBOX');
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!host.trim() || !username.trim() || !password) return setError('Server, username and password are all required');
    try {
      await connect.mutateAsync({ host: host.trim(), port, username: username.trim(), password, mailbox: mailbox.trim() || 'INBOX' });
      setPassword('');
      setEditing(false);
      toast({ title: 'Mailbox connected', body: 'Syncing recent mail…' });
      sync.mutate(undefined, { onError: (err) => toast({ title: 'First sync failed', body: errorMessage(err), tone: 'error' }) });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove() {
    const ok = await confirm({ title: 'Disconnect this mailbox?', body: 'Synced message headers are deleted from Daybook. Nothing changes in your mailbox.', confirmLabel: 'Disconnect', danger: true });
    if (ok) disconnect.mutate(undefined, { onSuccess: () => toast({ title: 'Mailbox disconnected' }) });
  }

  return (
    <section className="card">
      <h2>Email</h2>
      <p>Read-only IMAP. Daybook reads sender, subject, date and flags from the last 14 days. It never sends, deletes or marks mail as read.</p>
      {isLoading && <Skeleton lines={2} />}
      {account && !editing && (
        <>
          <div className="row">
            <span className="status-dot" style={{ background: account.last_error ? 'var(--danger)' : 'var(--ok)' }} />
            <div className="row-main">
              <div className="row-title">{account.username}</div>
              <div className="row-sub mono">
                {account.host}:{account.port} · {account.mailbox} · {account.last_synced_at ? `synced ${relativeFromNow(account.last_synced_at)}` : 'not synced yet'}
              </div>
              {account.last_error && <div className="field-error">{account.last_error}</div>}
            </div>
          </div>
          <div className="form-actions">
            <button className="btn btn-ghost btn-sm" onClick={remove}>
              Disconnect
            </button>
            <button
              className="btn btn-sm"
              onClick={() => {
                setHost(account.host);
                setPort(account.port);
                setUsername(account.username);
                setMailbox(account.mailbox);
                setEditing(true);
              }}
            >
              Change
            </button>
          </div>
        </>
      )}
      {(!account || editing) && !isLoading && (
        <form onSubmit={save}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {PRESETS.map((p) => (
              <button key={p.label} type="button" className="btn btn-sm btn-ghost" onClick={() => { setHost(p.host); setPort(993); }}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <label className="field">
              <span>IMAP server</span>
              <input className="input" value={host} onChange={(e) => setHost(e.target.value)} placeholder="imap.gmail.com" autoComplete="off" />
            </label>
            <label className="field">
              <span>Port</span>
              <input className="input" type="number" min={1} max={65535} value={port} onChange={(e) => setPort(Number(e.target.value))} />
            </label>
            <label className="field">
              <span>Username</span>
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </label>
            <label className="field">
              <span>App password</span>
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            </label>
            <label className="field span-2">
              <span>Mailbox</span>
              <input className="input" value={mailbox} onChange={(e) => setMailbox(e.target.value)} />
            </label>
          </div>
          <p className="muted" style={{ fontSize: '0.8rem' }}>
            Gmail, iCloud and Yahoo require an <b>app password</b> (not your normal password) with IMAP enabled. The password is checked against the server, then stored encrypted.
          </p>
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          <div className="form-actions">
            {editing && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>
                Cancel
              </button>
            )}
            <button className="btn btn-primary btn-sm" disabled={connect.isPending}>
              {connect.isPending ? 'Checking credentials…' : 'Connect'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

// --- AI & notifications ---------------------------------------------------------------

function AiCard() {
  const { data: meta } = useMeta();
  return (
    <section className="card">
      <h2>AI briefing</h2>
      {meta?.ai_enabled ? (
        <p>
          <span className="status-dot" style={{ background: 'var(--ok)' }} />
          Enabled. Briefings are written by <span className="mono">{meta.ai_model}</span>. Only titles, times, sender names and subjects are sent; never email bodies.
        </p>
      ) : (
        <p>
          <span className="status-dot" style={{ background: 'var(--muted)' }} />
          Not configured. Briefings use the rule-based summary. To let Claude write them, set <span className="mono">ANTHROPIC_API_KEY</span> in{' '}
          <span className="mono">PROJECT_01/.env</span> and restart the server.
        </p>
      )}
    </section>
  );
}

function NotificationsCard() {
  const supported = typeof Notification !== 'undefined';
  const [permission, setPermission] = useState(supported ? Notification.permission : 'denied');
  return (
    <section className="card">
      <h2>Notifications</h2>
      <p>Reminders always appear inside Daybook. Browser notifications also reach you when the tab is in the background.</p>
      {!supported ? (
        <p className="muted">This browser doesn’t support notifications.</p>
      ) : permission === 'granted' ? (
        <p>
          <span className="status-dot" style={{ background: 'var(--ok)' }} />
          Browser notifications are on.
        </p>
      ) : permission === 'denied' ? (
        <p className="muted">Notifications are blocked for this site. Allow them in your browser’s site settings.</p>
      ) : (
        <button className="btn btn-sm" onClick={() => Notification.requestPermission().then(setPermission)}>
          Enable browser notifications
        </button>
      )}
    </section>
  );
}
