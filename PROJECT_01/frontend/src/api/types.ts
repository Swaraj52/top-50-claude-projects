export type Priority = 'low' | 'medium' | 'high';
export type TaskStatus = 'todo' | 'done';
export type TaskView = 'today' | 'overdue' | 'upcoming' | 'all' | 'done';

export interface User {
  id: number;
  email: string;
  name: string;
  timezone: string;
}

export interface Task {
  id: number;
  title: string;
  notes: string;
  priority: Priority;
  status: TaskStatus;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TaskInput {
  title: string;
  notes?: string;
  priority?: Priority;
  due_date?: string | null;
}

export interface Reminder {
  id: number;
  text: string;
  remind_at: string;
  status: 'pending' | 'dismissed';
  task_id: number | null;
}

export interface CalendarEvent {
  id: number;
  title: string;
  location: string;
  description: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
  source_id: number | null;
  source_name: string | null;
  color: string;
  read_only: boolean;
}

export interface EventInput {
  title: string;
  start_at: string;
  end_at: string;
  all_day?: boolean;
  location?: string;
  description?: string;
}

export interface CalendarSource {
  id: number;
  name: string;
  kind: 'url' | 'file';
  color: string;
  last_synced_at: string | null;
  last_error: string | null;
  event_count: number;
}

export interface EmailAccount {
  host: string;
  port: number;
  username: string;
  mailbox: string;
  last_synced_at: string | null;
  last_error: string | null;
}

export interface EmailMessage {
  id: number;
  from_name: string;
  from_addr: string;
  subject: string;
  received_at: string;
  is_unread: boolean;
  is_flagged: boolean;
  task_id: number | null;
}

export interface DailyPriority {
  id: number;
  day: string;
  position: number;
  text: string;
  task_id: number | null;
  done: boolean;
}

export interface FocusItem {
  title: string;
  reason: string;
  task_id: number | null;
}

export interface Briefing {
  id: number;
  day: string;
  source: 'ai' | 'rule';
  model: string | null;
  note: string | null;
  content: {
    headline: string;
    summary: string;
    schedule_notes: string[];
    focus: FocusItem[];
    heads_up: string[];
  };
  created_at: string;
}

export interface Dashboard {
  date: string;
  timezone: string;
  user_name: string;
  events: CalendarEvent[];
  tasks: Task[];
  reminders: Reminder[];
  priorities: DailyPriority[];
  emails: EmailMessage[];
  email_connected: boolean;
  calendars_connected: number;
  counts: {
    overdue: number;
    due_today: number;
    done_today: number;
    upcoming: number;
    events_today: number;
    unread_emails: number;
    attention_emails: number;
  };
  briefing: Briefing | null;
}

export interface Meta {
  version: string;
  ai_enabled: boolean;
  ai_model: string | null;
}
