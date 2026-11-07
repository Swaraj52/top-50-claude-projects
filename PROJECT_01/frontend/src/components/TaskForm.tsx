import { useState, type FormEvent } from 'react';
import { errorMessage } from '../api/client';
import { useTaskMutations } from '../api/hooks';
import type { Priority, Task } from '../api/types';
import { Dialog } from './Dialog';
import { useFeedback } from './feedback';

interface Props {
  open: boolean;
  onClose: () => void;
  task?: Task | null;
  defaultDue?: string | null;
}

export function TaskForm({ open, onClose, task, defaultDue = null }: Props) {
  return (
    <Dialog open={open} onClose={onClose} title={task ? 'Edit task' : 'New task'}>
      {open && <TaskFormBody task={task ?? null} defaultDue={defaultDue} onClose={onClose} />}
    </Dialog>
  );
}

function TaskFormBody({ task, defaultDue, onClose }: { task: Task | null; defaultDue: string | null; onClose: () => void }) {
  const { create, update } = useTaskMutations();
  const { toast } = useFeedback();
  const [title, setTitle] = useState(task?.title ?? '');
  const [notes, setNotes] = useState(task?.notes ?? '');
  const [priority, setPriority] = useState<Priority>(task?.priority ?? 'medium');
  const [due, setDue] = useState(task?.due_date ?? defaultDue ?? '');
  const [error, setError] = useState<string | null>(null);
  const saving = create.isPending || update.isPending;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError('Give the task a title');
      return;
    }
    const body = { title: title.trim(), notes, priority, due_date: due || null };
    try {
      if (task) await update.mutateAsync({ id: task.id, ...body });
      else await create.mutateAsync(body);
      toast({ title: task ? 'Task updated' : 'Task added', body: body.title });
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <form className="dialog-body" onSubmit={submit} noValidate>
      <div className="form-grid">
        <label className="field span-2">
          <span>Title</span>
          <input
            className="input"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setError(null);
            }}
            maxLength={200}
            autoFocus
            aria-invalid={error ? true : undefined}
          />
        </label>
        <label className="field">
          <span>Due date</span>
          <input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <label className="field">
          <span>Priority</span>
          <select className="select" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <label className="field span-2">
          <span>Notes</span>
          <textarea className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} />
        </label>
      </div>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving…' : task ? 'Save changes' : 'Add task'}
        </button>
      </div>
    </form>
  );
}
