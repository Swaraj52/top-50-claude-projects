import { useEffect, useRef, useState, type FormEvent } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth, useMe, useStats } from '../api/hooks';

type Theme = 'system' | 'light' | 'dark';

function readTheme(): Theme {
  try {
    const t = localStorage.getItem('stacks-theme');
    return t === 'light' || t === 'dark' ? t : 'system';
  } catch {
    return 'system';
  }
}

export function Layout() {
  const { data: me } = useMe();
  const { data: stats } = useStats();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [q, setQ] = useState(location.pathname === '/search' ? (params.get('q') ?? '') : '');
  const [theme, setTheme] = useState<Theme>(readTheme);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('stacks-theme', theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
      if (e.key === '/' && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function search(e: FormEvent) {
    e.preventDefault();
    if (q.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand" aria-label="Stacks home">
            <span className="brand-mark" aria-hidden>
              LL
            </span>
            Stacks
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Inbox{stats && stats.inbox > 0 && <span className="count-badge" aria-label={`${stats.inbox} new`}>{stats.inbox}</span>}
            </NavLink>
            <NavLink to="/library">Library</NavLink>
            <NavLink to="/ask">Ask</NavLink>
            <NavLink to="/settings">Settings</NavLink>
          </nav>
          <form className="topsearch" onSubmit={search} role="search">
            <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
              <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="2" />
              <path d="M11 11l4 4" stroke="currentColor" strokeWidth="2" />
            </svg>
            <input ref={searchRef} className="input" placeholder="Search everything  /" aria-label="Search your library" value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setTheme(theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system')}
            aria-label={`Theme: ${theme}. Change theme`}
            title="Change theme"
          >
            {theme === 'dark' ? '☾' : theme === 'light' ? '☀' : '◐'}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => logout.mutate()} title={me?.email}>
            Sign out
          </button>
        </div>
      </header>
      <main className="main" id="main">
        <Outlet />
      </main>
    </>
  );
}
