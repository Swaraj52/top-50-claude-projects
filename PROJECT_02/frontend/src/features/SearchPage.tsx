import { Link, useSearchParams } from 'react-router-dom';
import { useSearch } from '../api/hooks';
import { Empty, ErrorNotice, Highlighted, Skeleton } from '../components/ui';
import { callNumber, hostOf, KIND_LABEL } from '../lib/format';

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const archived = params.get('archived') === '1';
  const { data, isLoading, error, refetch } = useSearch(q, archived);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Card catalogue</div>
          <h1>{q ? `“${q}”` : 'Search'}</h1>
        </div>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.9rem' }}>
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => {
              const next = new URLSearchParams(params);
              if (e.target.checked) next.set('archived', '1');
              else next.delete('archived');
              setParams(next, { replace: true });
            }}
          />
          Include archived
        </label>
      </div>

      {!q && <Empty title="Search your whole library">Type in the search box above (press <span className="kbd">/</span>). Titles, tags and full text are searched; word endings don’t matter.</Empty>}
      {isLoading && <Skeleton lines={5} />}
      {error && <ErrorNotice error={error} retry={() => refetch()} />}
      {data && (
        <>
          <p className="muted mono" style={{ fontSize: '0.82rem' }}>
            {data.hits.length} {data.hits.length === 1 ? 'result' : 'results'}
            {data.mode === 'any' && data.hits.length > 0 && ' · no item had every word, so these match any of them'}
          </p>
          {data.hits.length === 0 && (
            <Empty title="No matches" action={<Link className="btn btn-sm" to={`/ask?q=${encodeURIComponent(q)}`}>Ask your library instead</Link>}>
              Try fewer or different words.
            </Empty>
          )}
          <div style={{ maxWidth: 860 }}>
            {data.hits.map(({ item, snippet }) => (
              <div className="result" key={item.id}>
                <div className="mono muted" style={{ fontSize: '0.78rem' }}>
                  {callNumber(item.kind, item.id)} · {KIND_LABEL[item.kind]} · {item.source_name || hostOf(item.url)}
                  {item.status === 'archived' && ' · archived'}
                </div>
                <Link className="title" to={`/items/${item.id}`}>
                  {item.title}
                </Link>
                {snippet && (
                  <p className="snippet">
                    <Highlighted snippet={snippet} />
                  </p>
                )}
                {item.tags.length > 0 && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    {item.tags.map((t) => (
                      <Link key={t} className="stamp" to={`/library?status=all&tag=${encodeURIComponent(t)}`}>
                        {t}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
