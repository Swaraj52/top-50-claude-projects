import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useItem, useItemMutations, useMeta } from '../api/hooks';
import type { ItemDetail, Status } from '../api/types';
import { useFeedback } from '../components/feedback';
import { TagEditor } from '../components/TagEditor';
import { ErrorNotice, Skeleton, Spinner } from '../components/ui';
import { callNumber, hostOf, KIND_LABEL, timeAgo } from '../lib/format';

export function ItemPage() {
  const id = Number(useParams().id);
  const { data, isLoading, error, refetch } = useItem(id);
  if (isLoading) return <Skeleton lines={8} />;
  if (error || !data) return <ErrorNotice error={error ?? new Error('Item not found')} retry={() => refetch()} />;
  return <Reader item={data} />;
}

function Paragraphs({ text, video }: { text: string; video: boolean }) {
  return (
    <>
      {text.split(/\n\s*\n|\n/).filter((p) => p.trim()).map((p, i) => {
        const stamp = video ? p.match(/^\[(\d+(?::\d{2}){1,2})\]\s*/) : null;
        return (
          <p key={i}>
            {stamp && <span className="stamp-time">{stamp[1]}</span>}
            {stamp ? p.slice(stamp[0].length) : p}
          </p>
        );
      })}
    </>
  );
}

function Reader({ item }: { item: ItemDetail }) {
  const { data: meta } = useMeta();
  const { update, remove, summarize } = useItemMutations();
  const { toast, confirm } = useFeedback();
  const navigate = useNavigate();
  const [editingText, setEditingText] = useState(false);
  const [draft, setDraft] = useState(item.content);

  const patch = (body: Parameters<typeof update.mutate>[0]) =>
    update.mutate(body, { onError: (err) => toast({ title: 'Could not save', body: errorMessage(err), tone: 'error' }) });

  async function del() {
    const ok = await confirm({ title: 'Delete this item?', body: 'It will be removed from your library, search and future answers.', confirmLabel: 'Delete', danger: true });
    if (ok) remove.mutate(item.id, { onSuccess: () => { toast({ title: 'Deleted', body: item.title }); navigate('/library'); } });
  }

  async function runSummary() {
    try {
      const r = await summarize.mutateAsync(item.id);
      if (r.summary?.note) toast({ title: 'Summary ready (extractive)', body: r.summary.note, tone: 'error' });
    } catch (err) {
      toast({ title: 'Could not summarise', body: errorMessage(err), tone: 'error' });
    }
  }

  const s = item.summary;
  const source = item.source_name || hostOf(item.url);

  return (
    <div className="reader">
      <article>
        <div className="reader-head">
          <div className="eyebrow">
            {callNumber(item.kind, item.id)} · {KIND_LABEL[item.kind]}
          </div>
          <h1>{item.title}</h1>
          <div className="reader-meta">
            {source && <span>{source}</span>}
            {item.author && item.author !== source && <span>by {item.author}</span>}
            {item.published && <span>{item.published}</span>}
            {item.reading_minutes > 0 && <span>{item.reading_minutes} min</span>}
            <span>saved {timeAgo(item.created_at)}</span>
            {item.url && (
              <a href={item.url} target="_blank" rel="noreferrer noopener">
                Open original ↗
              </a>
            )}
          </div>
        </div>

        {item.kind === 'video' && !item.has_transcript && !editingText && (
          <div className="notice" style={{ marginTop: 18 }}>
            YouTube didn’t provide a transcript, so only the title is searchable.{' '}
            <button className="btn btn-sm" onClick={() => setEditingText(true)}>Paste transcript</button>
          </div>
        )}

        {editingText ? (
          <div style={{ marginTop: 22 }}>
            <textarea className="textarea" style={{ minHeight: 320 }} aria-label="Item text" value={draft} onChange={(e) => setDraft(e.target.value)} />
            <div className="form-actions">
              <button className="btn btn-ghost" onClick={() => { setEditingText(false); setDraft(item.content); }}>Cancel</button>
              <button
                className="btn btn-primary"
                disabled={update.isPending}
                onClick={() => update.mutate({ id: item.id, content: draft }, { onSuccess: () => { setEditingText(false); toast({ title: 'Text saved and re-indexed' }); } })}
              >
                Save text
              </button>
            </div>
          </div>
        ) : item.content ? (
          <div className="reader-body">
            <Paragraphs text={item.content} video={item.kind === 'video'} />
          </div>
        ) : (
          <p className="muted" style={{ marginTop: 24 }}>
            {item.description || 'No text was captured for this item.'}
          </p>
        )}
      </article>

      <aside className="side" aria-label="Item details">
        <section className="panel">
          <h2>
            Summary
            {s && (
              <span className={`source-pill ${s.source === 'ai' ? 'ai' : 'plain'}`}>
                {s.source === 'ai' ? `✦ Claude · ${s.model}` : 'Extractive, no AI'}
              </span>
            )}
          </h2>
          {s ? (
            <>
              {s.note && <div className="notice">{s.note}</div>}
              <p style={{ margin: 0, fontFamily: 'var(--serif)' }}>{s.tldr}</p>
              {s.key_points.length > 0 && (
                <ul>
                  {s.key_points.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="muted" style={{ margin: 0, fontSize: '0.9rem' }}>
              {meta?.ai_enabled ? `Claude (${meta.ai_model}) will write a TL;DR, key points and tag ideas.` : 'An extractive summary picks the most representative sentences. Add an ANTHROPIC_API_KEY for Claude-written summaries.'}
            </p>
          )}
          <button className="btn btn-sm" style={{ marginTop: 12 }} onClick={runSummary} disabled={summarize.isPending || (!item.content && !item.description)}>
            {summarize.isPending && <Spinner label="Summarising" />}
            {summarize.isPending ? 'Summarising…' : s ? 'Regenerate' : 'Summarize'}
          </button>
        </section>

        <section className="panel">
          <h2>Tags</h2>
          <TagEditor tags={item.tags} suggestions={s?.suggested_tags} busy={update.isPending} onChange={(tags) => patch({ id: item.id, tags })} />
        </section>

        <section className="panel">
          <h2>Filing</h2>
          <div className="seg" role="group" aria-label="Shelf">
            {(['inbox', 'library', 'archived'] as Status[]).map((st) => (
              <button key={st} aria-pressed={item.status === st} onClick={() => patch({ id: item.id, status: st })}>
                {st === 'inbox' ? 'Inbox' : st === 'library' ? 'Library' : 'Archived'}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
            <button className="btn btn-sm" aria-pressed={item.favorite} onClick={() => patch({ id: item.id, favorite: !item.favorite })}>
              {item.favorite ? '★ Favourite' : '☆ Favourite'}
            </button>
            {!editingText && (
              <button className="btn btn-sm" onClick={() => setEditingText(true)}>
                Edit text
              </button>
            )}
            <Link className="btn btn-sm" to={`/ask?about=${encodeURIComponent(item.title)}`}>
              Ask about this
            </Link>
            <button className="btn btn-sm btn-danger" onClick={del}>
              Delete
            </button>
          </div>
        </section>
      </aside>
    </div>
  );
}
