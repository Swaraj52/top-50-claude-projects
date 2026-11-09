import { useSearchParams } from 'react-router-dom';
import { useItems, useTags } from '../api/hooks';
import type { ItemFilters, Kind, Status } from '../api/types';
import { IndexCard } from '../components/IndexCard';
import { Empty, ErrorNotice, Skeleton } from '../components/ui';
import { KIND_LABEL } from '../lib/format';

const KINDS: Kind[] = ['article', 'video', 'newsletter', 'note', 'pdf'];

export function LibraryPage() {
  const [params, setParams] = useSearchParams();
  const filters: ItemFilters = {
    status: (params.get('status') as Status | 'all' | null) ?? 'library',
    kind: (params.get('kind') as Kind | null) ?? undefined,
    tag: params.get('tag') ?? undefined,
    favorite: params.get('fav') === '1' ? true : undefined,
    sort: (params.get('sort') as ItemFilters['sort']) ?? 'newest',
  };
  const { data, isLoading, error, refetch } = useItems(filters);
  const { data: tags } = useTags();

  function set(key: string, value: string | undefined) {
    const next = new URLSearchParams(params);
    if (value === undefined || value === '') next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  }

  const filtered = Boolean(filters.kind || filters.tag || filters.favorite);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">The stacks</div>
          <h1>Library</h1>
        </div>
        <select className="select" style={{ width: 'auto' }} aria-label="Sort" value={filters.sort} onChange={(e) => set('sort', e.target.value === 'newest' ? undefined : e.target.value)}>
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="title">Title A–Z</option>
        </select>
      </div>

      <div className="filters">
        <div className="seg" role="group" aria-label="Shelf">
          {(['library', 'archived', 'all'] as const).map((s) => (
            <button key={s} aria-pressed={filters.status === s} onClick={() => set('status', s === 'library' ? undefined : s)}>
              {s === 'library' ? 'Library' : s === 'archived' ? 'Archived' : 'Everything'}
            </button>
          ))}
        </div>
        <div className="seg" role="group" aria-label="Type">
          <button aria-pressed={!filters.kind} onClick={() => set('kind', undefined)}>All types</button>
          {KINDS.map((k) => (
            <button key={k} aria-pressed={filters.kind === k} onClick={() => set('kind', filters.kind === k ? undefined : k)}>
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
        <button className="btn btn-sm" aria-pressed={!!filters.favorite} onClick={() => set('fav', filters.favorite ? undefined : '1')} style={filters.favorite ? { borderColor: 'var(--brass)', color: 'var(--brass)' } : undefined}>
          ★ Favourites
        </button>
      </div>

      {tags && tags.length > 0 && (
        <div className="tagcloud" aria-label="Tags">
          {tags.map((t) => (
            <button
              key={t.id}
              className={`stamp ${filters.tag === t.name ? 'brass' : ''}`}
              aria-pressed={filters.tag === t.name}
              onClick={() => set('tag', filters.tag === t.name ? undefined : t.name)}
            >
              {t.name} · {t.count}
            </button>
          ))}
        </div>
      )}

      {isLoading && <Skeleton lines={5} />}
      {error && <ErrorNotice error={error} retry={() => refetch()} />}
      {data && data.items.length === 0 && (
        <Empty
          title={filtered ? 'Nothing matches these filters' : filters.status === 'archived' ? 'Nothing archived' : 'Your library is empty'}
          action={filtered ? <button className="btn btn-sm" onClick={() => setParams({})}>Clear filters</button> : undefined}
        >
          {!filtered && filters.status === 'library' && 'Save something from the Inbox and press Keep to shelve it here.'}
        </Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <p className="muted mono" style={{ fontSize: '0.82rem', marginTop: 0 }}>
            {data.total} {data.total === 1 ? 'card' : 'cards'}
            {filters.tag && ` tagged “${filters.tag}”`}
          </p>
          <div className="cards">
            {data.items.map((item) => (
              <IndexCard key={item.id} item={item} mode="library" onTag={(t) => set('tag', t)} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
