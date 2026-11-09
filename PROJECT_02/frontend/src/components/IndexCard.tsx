import { Link } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useItemMutations } from '../api/hooks';
import type { ItemCard } from '../api/types';
import { callNumber, hostOf, KIND_LABEL, timeAgo } from '../lib/format';
import { useFeedback } from './feedback';

interface Props {
  item: ItemCard;
  /** Inbox cards get triage buttons; library cards get a favourite toggle. */
  mode: 'inbox' | 'library';
  onTag?: (tag: string) => void;
}

export function IndexCard({ item, mode, onTag }: Props) {
  const { update, remove } = useItemMutations();
  const { toast, confirm } = useFeedback();
  const source = item.source_name || hostOf(item.url) || KIND_LABEL[item.kind];

  const move = (status: 'library' | 'archived', label: string) =>
    update.mutate(
      { id: item.id, status },
      {
        onSuccess: () => toast({ title: label, body: item.title, actions: [{ label: 'Undo', onClick: () => update.mutate({ id: item.id, status: item.status }) }] }),
        onError: (err) => toast({ title: 'Could not update', body: errorMessage(err), tone: 'error' }),
      },
    );

  async function del() {
    const ok = await confirm({ title: 'Delete this item?', body: `“${item.title}” and its summary will be removed from your library.`, confirmLabel: 'Delete', danger: true });
    if (ok) remove.mutate(item.id, { onSuccess: () => toast({ title: 'Deleted', body: item.title }) });
  }

  return (
    <article className="icard" aria-label={item.title}>
      <div className="icard-top">
        <span title="Call number">{callNumber(item.kind, item.id)}</span>
        {mode === 'library' ? (
          <button
            className="fav"
            aria-pressed={item.favorite}
            aria-label={item.favorite ? `Unfavourite “${item.title}”` : `Favourite “${item.title}”`}
            onClick={() => update.mutate({ id: item.id, favorite: !item.favorite })}
          >
            ★
          </button>
        ) : (
          <span>{timeAgo(item.created_at)}</span>
        )}
      </div>
      {item.kind === 'video' && item.thumbnail_url?.startsWith('https://i.ytimg.com/') && (
        <img className="icard-thumb" src={item.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
      )}
      <Link to={`/items/${item.id}`} className="icard-title">
        {item.title}
      </Link>
      <div className="icard-meta">
        {KIND_LABEL[item.kind]} · {source}
        {item.reading_minutes > 0 && ` · ${item.reading_minutes} min ${item.kind === 'video' ? 'transcript' : 'read'}`}
        {item.kind === 'video' && !item.has_transcript && ' · no transcript'}
      </div>
      {item.tldr && <p className="icard-tldr" style={{ margin: 0 }}>{item.tldr}</p>}
      <div className="icard-foot">
        {item.tags.map((t) =>
          onTag ? (
            <button key={t} className="stamp" onClick={() => onTag(t)} aria-label={`Filter by tag ${t}`}>
              {t}
            </button>
          ) : (
            <span key={t} className="stamp static">
              {t}
            </span>
          ),
        )}
        {mode === 'inbox' && (
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
            <button className="btn btn-sm btn-primary" onClick={() => move('library', 'Kept in library')} disabled={update.isPending}>
              Keep
            </button>
            <button className="btn btn-sm" onClick={() => move('archived', 'Archived')} disabled={update.isPending}>
              Archive
            </button>
            <button className="btn btn-sm btn-ghost" onClick={del} aria-label={`Delete “${item.title}”`}>
              ✕
            </button>
          </span>
        )}
      </div>
    </article>
  );
}
