import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTasks, useTz } from '../api/hooks';
import type { Task, TaskView } from '../api/types';
import { TaskForm } from '../components/TaskForm';
import { TaskRow } from '../components/TaskRow';
import { Empty, ErrorNotice, Skeleton } from '../components/ui';
import { todayIn } from '../lib/dates';

const VIEWS: { value: TaskView; label: string; empty: string }[] = [
  { value: 'today', label: 'Today', empty: 'Nothing due today.' },
  { value: 'overdue', label: 'Overdue', empty: 'Nothing overdue. Nicely done.' },
  { value: 'upcoming', label: 'Upcoming', empty: 'No dated tasks ahead.' },
  { value: 'all', label: 'All open', empty: 'No open tasks. Add one to get started.' },
  { value: 'done', label: 'Done', empty: 'Completed tasks will show up here.' },
];

export function TasksPage() {
  const tz = useTz();
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.value === params.get('view'))?.value ?? 'all') as TaskView;
  const { data, isLoading, error, refetch } = useTasks(view);
  const [editing, setEditing] = useState<Task | null | 'new'>(null);
  const today = todayIn(tz);
  const meta = VIEWS.find((v) => v.value === view)!;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="kicker">Task tracker</div>
          <h1>Tasks</h1>
        </div>
        <button className="btn btn-primary" onClick={() => setEditing('new')}>
          New task
        </button>
      </header>

      <div className="tabs" role="tablist" aria-label="Task views">
        {VIEWS.map((v) => (
          <button
            key={v.value}
            role="tab"
            className="tab"
            aria-selected={v.value === view}
            onClick={() => setParams(v.value === 'all' ? {} : { view: v.value })}
          >
            {v.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" style={{ maxWidth: 820 }}>
        {isLoading && <Skeleton lines={5} />}
        {error && <ErrorNotice error={error} retry={() => refetch()} />}
        {data && data.length === 0 && (
          <Empty
            title={meta.empty}
            action={
              view !== 'done' && (
                <button className="btn btn-sm" onClick={() => setEditing('new')}>
                  Add a task
                </button>
              )
            }
          />
        )}
        {data?.map((t) => <TaskRow key={t.id} task={t} today={today} onEdit={setEditing} />)}
        {data && data.length > 0 && (
          <p className="muted mono" style={{ fontSize: '0.75rem' }}>
            {data.length} {data.length === 1 ? 'task' : 'tasks'}
          </p>
        )}
      </div>

      <TaskForm
        open={editing !== null}
        task={editing === 'new' ? null : editing}
        defaultDue={view === 'today' ? today : null}
        onClose={() => setEditing(null)}
      />
    </>
  );
}
