import { useEffect, useRef, useState } from 'react';
import { errorMessage } from '../api/client';
import { useMe, useMeta, useTagMutations, useTags } from '../api/hooks';
import type { Tag } from '../api/types';
import { useFeedback } from '../components/feedback';
import { Skeleton } from '../components/ui';

export function SettingsPage() {
  const { data: me } = useMe();
  const { data: meta } = useMeta();
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Library card</div>
          <h1>Settings</h1>
        </div>
      </div>
      <div className="grid-2">
        <div style={{ display: 'grid', gap: 20 }}>
          <section className="panel">
            <h2>Account</h2>
            <p style={{ margin: 0 }}>
              <b>{me?.name}</b>
              <br />
              <span className="muted">{me?.email}</span>
            </p>
          </section>
          <section className="panel">
            <h2>Claude</h2>
            {meta?.ai_enabled ? (
              <p style={{ margin: 0 }}>
                Connected: summaries and answers are written by <span className="mono">{meta.ai_model}</span>. Text is sent only when you press
                Summarize or ask a question.
              </p>
            ) : (
              <p style={{ margin: 0 }}>
                Not configured. Summaries are extractive and Ask shows the most relevant passages. To use Claude, set{' '}
                <span className="mono">ANTHROPIC_API_KEY</span> in <span className="mono">PROJECT_02/.env</span> and restart the server.
              </p>
            )}
          </section>
          <Bookmarklet />
        </div>
        <TagManager />
      </div>
    </>
  );
}

function Bookmarklet() {
  const link = useRef<HTMLAnchorElement>(null);
  const target = `${window.location.origin}/?add=`;
  useEffect(() => {
    // React refuses javascript: URLs in JSX, so set it on the element directly.
    link.current?.setAttribute('href', `javascript:location.href='${target}'+encodeURIComponent(location.href)`);
  }, [target]);
  return (
    <section className="panel">
      <h2>Save from any page</h2>
      <p style={{ marginTop: 0, fontSize: '0.92rem' }}>
        Drag this button to your bookmarks bar. On any article or YouTube video, click it to open Stacks with the link ready to save.
      </p>
      <a ref={link} className="btn btn-primary" onClick={(e) => e.preventDefault()} title="Drag me to your bookmarks bar">
        + Save to Stacks
      </a>
      <p className="muted" style={{ fontSize: '0.8rem', marginBottom: 0 }}>
        It only opens this app with the page address filled in; nothing is saved until you press Save.
      </p>
    </section>
  );
}

function TagManager() {
  const { data, isLoading } = useTags();
  return (
    <section className="panel">
      <h2>Tags</h2>
      {isLoading && <Skeleton lines={3} />}
      {data?.length === 0 && <p className="muted" style={{ margin: 0 }}>No tags yet. Add them while saving or on any item.</p>}
      {data?.map((t) => <TagRow key={t.id} tag={t} />)}
      {data && data.length > 0 && (
        <p className="muted" style={{ fontSize: '0.8rem', marginBottom: 0 }}>
          Renaming a tag to an existing name merges the two.
        </p>
      )}
    </section>
  );
}

function TagRow({ tag }: { tag: Tag }) {
  const { rename, remove } = useTagMutations();
  const { toast, confirm } = useFeedback();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(tag.name);

  return (
    <div className="row">
      {editing ? (
        <form
          style={{ display: 'flex', gap: 6, flex: 1 }}
          onSubmit={(e) => {
            e.preventDefault();
            rename.mutate(
              { id: tag.id, name },
              {
                onSuccess: (t) => { setEditing(false); toast({ title: 'Tag renamed', body: t.name }); },
                onError: (err) => toast({ title: 'Could not rename', body: errorMessage(err), tone: 'error' }),
              },
            );
          }}
        >
          <input className="input" style={{ padding: '5px 9px' }} aria-label={`New name for ${tag.name}`} value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={40} />
          <button className="btn btn-sm btn-primary" disabled={!name.trim()}>Save</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setEditing(false); setName(tag.name); }}>Cancel</button>
        </form>
      ) : (
        <>
          <span className="stamp static">{tag.name}</span>
          <span className="muted mono" style={{ fontSize: '0.8rem' }}>{tag.count} {tag.count === 1 ? 'item' : 'items'}</span>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 2 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>Rename</button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={async () => {
                if (await confirm({ title: `Delete tag “${tag.name}”?`, body: 'Items keep their content; only the tag is removed.', confirmLabel: 'Delete tag', danger: true })) {
                  remove.mutate(tag.id, { onSuccess: () => toast({ title: 'Tag deleted' }) });
                }
              }}
            >
              Delete
            </button>
          </span>
        </>
      )}
    </div>
  );
}
