import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';
import type {
  Briefing,
  CalendarEvent,
  CalendarSource,
  DailyPriority,
  Dashboard,
  EmailAccount,
  EmailMessage,
  EventInput,
  Meta,
  Reminder,
  Task,
  TaskInput,
  TaskView,
  User,
} from './types';

export const keys = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  dashboard: ['dashboard'] as const,
  tasks: (view: TaskView) => ['tasks', view] as const,
  reminders: ['reminders'] as const,
  events: (start: string, end: string) => ['events', start, end] as const,
  calendars: ['calendars'] as const,
  emailAccount: ['email', 'account'] as const,
  emails: (filter: string) => ['email', 'messages', filter] as const,
};

/** After any write, refresh everything that summarises it. */
function useInvalidate() {
  const qc = useQueryClient();
  return (...prefixes: string[]) =>
    Promise.all(['dashboard', ...prefixes].map((p) => qc.invalidateQueries({ queryKey: [p] })));
}

// --- session ---------------------------------------------------------------------------

export function useMe() {
  return useQuery<User | null>({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api<User>('/auth/me');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: Infinity,
  });
}

/** The signed-in user's profile timezone; everything date-related is computed in it. */
export function useTz(): string {
  const { data } = useMe();
  return data?.timezone ?? (Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
}

export function useMeta() {
  return useQuery({ queryKey: keys.meta, queryFn: () => api<Meta>('/meta'), staleTime: Infinity });
}

export function useAuth() {
  const qc = useQueryClient();
  const onSignedIn = (user: User) => {
    qc.clear();
    qc.setQueryData(keys.me, user);
  };
  return {
    login: useMutation({
      mutationFn: (body: { email: string; password: string }) =>
        api<User>('/auth/login', { method: 'POST', body }),
      onSuccess: onSignedIn,
    }),
    register: useMutation({
      mutationFn: (body: { email: string; password: string; name: string; timezone: string }) =>
        api<User>('/auth/register', { method: 'POST', body }),
      onSuccess: onSignedIn,
    }),
    logout: useMutation({
      mutationFn: () => api<void>('/auth/logout', { method: 'POST' }),
      onSuccess: () => {
        qc.clear();
        qc.setQueryData(keys.me, null);
      },
    }),
  };
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; timezone?: string }) => api<User>('/auth/me', { method: 'PATCH', body }),
    onSuccess: (user) => {
      qc.setQueryData(keys.me, user);
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' });
    },
  });
}

// --- dashboard & briefing ---------------------------------------------------------------

export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard, queryFn: () => api<Dashboard>('/dashboard/today'), refetchInterval: 5 * 60_000 });
}

export function useGenerateBriefing() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: () => api<Briefing>('/briefing', { method: 'POST' }),
    onSuccess: () => invalidate(),
  });
}

// --- tasks -------------------------------------------------------------------------------

export function useTasks(view: TaskView) {
  return useQuery({ queryKey: keys.tasks(view), queryFn: () => api<Task[]>(`/tasks?view=${view}`) });
}

export function useTaskMutations() {
  const invalidate = useInvalidate();
  const done = () => invalidate('tasks', 'priorities');
  return {
    create: useMutation({ mutationFn: (body: TaskInput) => api<Task>('/tasks', { method: 'POST', body: { ...body } }), onSuccess: done }),
    update: useMutation({
      mutationFn: ({ id, ...body }: Partial<Task> & { id: number }) => api<Task>(`/tasks/${id}`, { method: 'PATCH', body }),
      onSuccess: done,
    }),
    remove: useMutation({ mutationFn: (id: number) => api<void>(`/tasks/${id}`, { method: 'DELETE' }), onSuccess: done }),
  };
}

// --- reminders ---------------------------------------------------------------------------

export function useReminders() {
  return useQuery({ queryKey: keys.reminders, queryFn: () => api<Reminder[]>('/reminders') });
}

export function useDueReminders(enabled: boolean) {
  return useQuery({
    queryKey: ['reminders', 'due'],
    queryFn: () => api<Reminder[]>('/reminders/due'),
    enabled,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
  });
}

export function useReminderMutations() {
  const invalidate = useInvalidate();
  const done = () => invalidate('reminders');
  return {
    create: useMutation({
      mutationFn: (body: { text: string; remind_at: string }) => api<Reminder>('/reminders', { method: 'POST', body }),
      onSuccess: done,
    }),
    snooze: useMutation({
      mutationFn: ({ id, minutes }: { id: number; minutes: number }) =>
        api<Reminder>(`/reminders/${id}/snooze`, { method: 'POST', body: { minutes } }),
      onSuccess: done,
    }),
    dismiss: useMutation({ mutationFn: (id: number) => api<Reminder>(`/reminders/${id}/dismiss`, { method: 'POST' }), onSuccess: done }),
    remove: useMutation({ mutationFn: (id: number) => api<void>(`/reminders/${id}`, { method: 'DELETE' }), onSuccess: done }),
  };
}

// --- events & calendars -------------------------------------------------------------------

export function useEvents(start: string, end: string) {
  return useQuery({
    queryKey: keys.events(start, end),
    queryFn: () => api<CalendarEvent[]>(`/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
  });
}

export function useEventMutations() {
  const invalidate = useInvalidate();
  const done = () => invalidate('events');
  return {
    create: useMutation({ mutationFn: (body: EventInput) => api<CalendarEvent>('/events', { method: 'POST', body: { ...body } }), onSuccess: done }),
    update: useMutation({
      mutationFn: ({ id, ...body }: Partial<EventInput> & { id: number }) => api<CalendarEvent>(`/events/${id}`, { method: 'PATCH', body }),
      onSuccess: done,
    }),
    remove: useMutation({ mutationFn: (id: number) => api<void>(`/events/${id}`, { method: 'DELETE' }), onSuccess: done }),
  };
}

export function useCalendars() {
  return useQuery({ queryKey: keys.calendars, queryFn: () => api<CalendarSource[]>('/calendars') });
}

export function useCalendarMutations() {
  const invalidate = useInvalidate();
  const done = () => invalidate('calendars', 'events');
  return {
    subscribe: useMutation({
      mutationFn: (body: { name: string; url: string; color: string }) => api<CalendarSource>('/calendars', { method: 'POST', body }),
      onSuccess: done,
    }),
    upload: useMutation({
      mutationFn: (form: FormData) => api<CalendarSource>('/calendars/upload', { method: 'POST', body: form }),
      onSuccess: done,
    }),
    sync: useMutation({
      mutationFn: (id: number) => api<CalendarSource>(`/calendars/${id}/sync`, { method: 'POST' }),
      onSettled: done,
    }),
    remove: useMutation({ mutationFn: (id: number) => api<void>(`/calendars/${id}`, { method: 'DELETE' }), onSuccess: done }),
  };
}

// --- email -------------------------------------------------------------------------------

export function useEmailAccount() {
  return useQuery({ queryKey: keys.emailAccount, queryFn: () => api<EmailAccount | null>('/email/account') });
}

export function useEmails(filter: 'attention' | 'unread' | 'all', enabled = true) {
  return useQuery({ queryKey: keys.emails(filter), queryFn: () => api<EmailMessage[]>(`/email/messages?filter=${filter}`), enabled });
}

export function useEmailMutations() {
  const invalidate = useInvalidate();
  const done = () => invalidate('email');
  return {
    connect: useMutation({
      mutationFn: (body: { host: string; port: number; username: string; password: string; mailbox: string }) =>
        api<EmailAccount>('/email/account', { method: 'PUT', body }),
      onSuccess: done,
    }),
    disconnect: useMutation({ mutationFn: () => api<void>('/email/account', { method: 'DELETE' }), onSuccess: done }),
    sync: useMutation({
      mutationFn: () => api<{ fetched: number; attention: number }>('/email/sync', { method: 'POST' }),
      onSettled: done,
    }),
    makeTask: useMutation({
      mutationFn: (id: number) => api<Task>(`/email/messages/${id}/task`, { method: 'POST' }),
      onSuccess: () => invalidate('email', 'tasks'),
    }),
  };
}

// --- priorities ------------------------------------------------------------------------------

export function usePriorityMutations() {
  const invalidate = useInvalidate();
  const done = () => invalidate('tasks', 'priorities');
  return {
    set: useMutation({
      mutationFn: (body: { day: string; items: { text: string; task_id: number | null; done: boolean }[] }) =>
        api<DailyPriority[]>('/priorities', { method: 'PUT', body }),
      onSuccess: done,
    }),
    toggle: useMutation({
      mutationFn: ({ id, done: isDone }: { id: number; done: boolean }) =>
        api<DailyPriority>(`/priorities/${id}`, { method: 'PATCH', body: { done: isDone } }),
      onSuccess: done,
    }),
  };
}
