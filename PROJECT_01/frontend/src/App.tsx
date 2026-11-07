import { Component, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useMe } from './api/hooks';
import { Layout } from './components/Layout';
import { Skeleton } from './components/ui';
import { AuthPage } from './features/AuthPage';
import { CalendarPage } from './features/CalendarPage';
import { InboxPage } from './features/InboxPage';
import { SettingsPage } from './features/SettingsPage';
import { TasksPage } from './features/TasksPage';
import { TodayPage } from './features/TodayPage';

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
          <button className="btn" onClick={() => location.reload()}>
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export function App() {
  const { data: me, isLoading, error } = useMe();

  if (isLoading) {
    return (
      <div className="main">
        <Skeleton lines={4} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="main">
        <div className="notice error" role="alert">
          {error.message}
        </div>
      </div>
    );
  }
  if (!me) return <AuthPage />;

  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<TodayPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="inbox" element={<InboxPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
