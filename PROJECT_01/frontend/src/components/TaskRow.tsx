import { errorMessage } from '../api/client';
import { useTaskMutations } from '../api/hooks';
import type { Task } from '../api/types';
import { dueLabel } from '../lib/dates';
import { useFeedback } from './feedback';
import { PriorityDot } from './ui';

export function TaskRow({ task, today, onEdit }: { task: Task; today: string; onEdit: (t: Task) => void }) {
  const { update, remove } = useTaskMutations();
  const { toast, confirm } = useFeedback();
  const done = task.status === 'done';
  const due = dueLabel(task.due_date, today);

  async function toggle() {
    try {
      await update.mutateAsync({ id: task.id, status: done ? 'todo' : 'done' });
      if (!done) toast({ title: 'Done', body: task.title, actions: [{ label: 'Undo', onClick: () => update.mutate({ id: task.id, status: 'todo' }) }] });
    } catch (err) {
      toast({ title: 'Could not update task', body: errorMessage(err), tone: 'error' });
    }
  }

  async function del() {
    const ok = await confirm({ title: 'Delete this task?', body: `“${task.title}” will be removed permanently.`, confirmLabel: 'Delete', danger: true });
    if (!ok) return;
    try {
      await remove.mutateAsync(task.id);
      toast({ title: 'Task deleted' });
    } catch (err) {
      toast({ title: 'Could not delete task', body: errorMessage(err), tone: 'error' });
    }
  }

  return (
    <div className="row">
      <input
        type="checkbox"
        className="check"
        checked={done}
        onChange={toggle}
        disabled={update.isPending}
        aria-label={done ? `Mark “${task.title}” as not done` : `Complete “${task.title}”`}
      />
      <div className="row-main">
        <div className={`row-title ${done ? 'done' : ''}`}>{task.title}</div>
        <div className="row-sub">
          <PriorityDot priority={task.priority} />
          {!done && due.tone !== 'none' && <span className={`chip ${due.tone}`}>{due.text}</span>}
          {task.notes && <span title={task.notes}>· notes</span>}
        </div>
      </div>
      <div className="row-actions">
        <button className="btn btn-ghost btn-sm" onClick={() => onEdit(task)} aria-label={`Edit “${task.title}”`}>
          Edit
        </button>
        <button className="btn btn-ghost btn-sm" onClick={del} aria-label={`Delete “${task.title}”`}>
          Delete
        </button>
      </div>
    </div>
  );
}
