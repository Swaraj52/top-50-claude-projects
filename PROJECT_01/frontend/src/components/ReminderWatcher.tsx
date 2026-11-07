import { useEffect, useRef } from 'react';
import { useDueReminders, useReminderMutations } from '../api/hooks';
import { useFeedback } from './feedback';

/** Polls for due reminders and raises an in-app toast plus a browser notification. */
export function ReminderWatcher() {
  const { data } = useDueReminders(true);
  const { snooze, dismiss } = useReminderMutations();
  const { toast, dismissToast } = useFeedback();
  const alerted = useRef(new Set<string>());

  useEffect(() => {
    if (!data) return;
    // A reminder handled elsewhere (dashboard, snoozed in another tab) loses its toast.
    const dueKeys = new Set(data.map((r) => `${r.id}@${r.remind_at}`));
    for (const key of alerted.current) {
      if (!dueKeys.has(key)) {
        alerted.current.delete(key);
        dismissToast(`reminder-${key.split('@')[0]}`);
      }
    }
    for (const r of data) {
      const key = `${r.id}@${r.remind_at}`;
      if (alerted.current.has(key)) continue;
      alerted.current.add(key);
      toast({
        id: `reminder-${r.id}`,
        title: 'Reminder',
        body: r.text,
        tone: 'reminder',
        sticky: true,
        actions: [
          { label: 'Snooze 10 min', onClick: () => snooze.mutate({ id: r.id, minutes: 10 }) },
          { label: '1 hour', onClick: () => snooze.mutate({ id: r.id, minutes: 60 }) },
          { label: 'Done', onClick: () => dismiss.mutate(r.id) },
        ],
      });
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted' && document.visibilityState !== 'visible') {
        try {
          new Notification('Reminder', { body: r.text, tag: `reminder-${r.id}` });
        } catch {
          /* some browsers only allow notifications from a service worker */
        }
      }
    }
  }, [data, toast, dismissToast, snooze, dismiss]);

  return null;
}
