import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth, useDashboard, useMe } from '../api/hooks';
import { CommandBar } from './CommandBar';
import { ReminderWatcher } from './ReminderWatcher';

type Theme = 'system' | 'light' | 'dark';

function readTheme(): Theme {
  try {
    const t = localStorage.getItem('daybook-theme');
    return t === 'light' || t === 'dark' ? t : 'system';
  } catch {
    return 'system';
  }
}

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    if (theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('daybook-theme', theme);
    } catch {
      /* storage unavailable: theme still applies for this visit */
    }
  }, [theme]);
  const next = () => setTheme((t) => (t === 'system' ? 'light' : t === 'light' ? 'dark' : 'system'));
  return [theme, next];
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

export function Layout() {
  const { data: me } = useMe();
  const { data: dash } = useDashboard();
  const { logout } = useAuth();
  const [commandOpen, setCommandOpen] = useState(false);
  const [theme, cycleTheme] = useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const attention = dash?.counts.attention_emails ?? 0;
  const due = (dash?.counts.overdue ?? 0) + (dash?.counts.due_today ?? 0);

  return (
    <div className="shell">
      <aside className="rail">
        <NavLink to="/" className="brand" aria-label="Daybook home">
          Daybook<span className="brand-dot" aria-hidden />
        </NavLink>
        <nav className="nav" aria-label="Main">
          <NavLink to="/" end>
            Today
          </NavLink>
          <NavLink to="/tasks">
            Tasks{due > 0 && <span className="nav-badge" aria-label={`${due} due`}>{due}</span>}
          </NavLink>
          <NavLink to="/calendar">Calendar</NavLink>
          <NavLink to="/inbox">
            Inbox{attention > 0 && <span className="nav-badge" aria-label={`${attention} need attention`}>{attention}</span>}
          </NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        <div className="rail-foot">
          <button className="btn btn-primary" onClick={() => setCommandOpen(true)}>
            Quick add <span className="kbd">{isMac ? '⌘' : 'Ctrl'} K</span>
          </button>
          <button className="btn btn-ghost btn-sm" onClick={cycleTheme} aria-label={`Theme: ${theme}. Change theme`}>
            Theme: {theme === 'system' ? 'Auto' : theme === 'light' ? 'Morning' : 'Night'}
          </button>
          <p className="credit">Built by Swayam</p>
          <div className="rail-user">
            <span title={me?.email} style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {me?.name}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={() => logout.mutate()}>
              Sign out
            </button>
          </div>
        </div>
      </aside>
      <main className="main" id="main">
        <Outlet />
      </main>
      <button className="btn btn-primary fab" onClick={() => setCommandOpen(true)} aria-label="Quick add">
        +
      </button>
      <CommandBar open={commandOpen} onClose={() => setCommandOpen(false)} />
      <ReminderWatcher />
    </div>
  );
}
