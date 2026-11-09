import { Component, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useMe } from './api/hooks';
import { Layout } from './components/Layout';
import { Skeleton } from './components/ui';
import { AskPage } from './features/AskPage';
import { AuthPage } from './features/AuthPage';
import { InboxPage } from './features/InboxPage';
import { ItemPage } from './features/ItemPage';
import { LibraryPage } from './features/LibraryPage';
import { SearchPage } from './features/SearchPage';
import { SettingsPage } from './features/SettingsPage';

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="main" role="alert">
          <h1>Something broke on this page.</h1>
          <p className="muted">{this.state.error.message}</p>
          <button className="btn" onClick={() => location.reload()}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export function App() {
  const { data: me, isLoading, error } = useMe();
  if (isLoading) return <div className="main"><Skeleton lines={4} /></div>;
  if (error) return <div className="main"><div className="notice error" role="alert">{error.message}</div></div>;
  if (!me) return <AuthPage />;
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<InboxPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="items/:id" element={<ItemPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="ask" element={<AskPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
