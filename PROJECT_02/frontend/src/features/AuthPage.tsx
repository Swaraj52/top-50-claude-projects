import { useState, type FormEvent } from 'react';
import { errorMessage } from '../api/client';
import { useAuth } from '../api/hooks';

export function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const { login, register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const pending = login.isPending || register.isPending;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.includes('@')) return setError('Enter a valid email address');
    if (mode === 'register') {
      if (!name.trim()) return setError('Tell us your name');
      if (password.length < 8) return setError('Use at least 8 characters for the password');
    }
    try {
      if (mode === 'login') await login.mutateAsync({ email, password });
      else await register.mutateAsync({ email, password, name: name.trim() });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="auth">
      <div className="auth-art">
        <div className="brand" style={{ color: 'inherit' }}>
          <span className="brand-mark" aria-hidden style={{ background: '#f2f0e4', color: '#1d4a37' }}>LL</span>
          Stacks
        </div>
        <h1>Everything you’ve read, ready to answer back.</h1>
        <div className="catalog" aria-hidden>
          <div><span className="mono">ART 0042</span>Why sleep matters for memory</div>
          <div><span className="mono">VID 0107</span>How habits rewire the brain</div>
          <div><span className="mono">NWS 0213</span>Markets: inflation cools again</div>
        </div>
        <p style={{ margin: 0, opacity: 0.85 }}>Save articles, YouTube videos, newsletters and PDFs. Search them all, then ask questions with cited answers.</p>
      </div>
      <form className="auth-form" onSubmit={submit} noValidate>
        <div>
          <div className="eyebrow">{mode === 'login' ? 'Welcome back' : 'Get a library card'}</div>
          <h2 style={{ fontSize: '2rem' }}>{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
        </div>
        {mode === 'register' && (
          <label className="field">
            <span>Name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} />
          </label>
        )}
        <label className="field">
          <span>Email</span>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </label>
        <label className="field">
          <span>Password</span>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        </label>
        {error && <div className="notice error" role="alert">{error}</div>}
        <button type="submit" className="btn btn-primary" disabled={pending}>
          {pending ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
        <p className="muted" style={{ fontSize: '0.9rem', margin: 0 }}>
          {mode === 'login' ? 'New here? ' : 'Already have an account? '}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}>
            {mode === 'login' ? 'Create an account' : 'Sign in instead'}
          </button>
        </p>
      </form>
    </div>
  );
}
