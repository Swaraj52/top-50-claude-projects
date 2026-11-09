import { useSearchParams } from 'react-router-dom';
import { useItems, useMe, useStats } from '../api/hooks';
import { AddBar } from '../components/AddBar';
import { IndexCard } from '../components/IndexCard';
import { Empty, ErrorNotice, Skeleton } from '../components/ui';

export function InboxPage() {
  const [params] = useSearchParams();
  const { data: me } = useMe();
  const { data: stats } = useStats();
  const { data, isLoading, error, refetch } = useItems({ status: 'inbox' });

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">New arrivals</div>
          <h1>{me ? `${me.name.split(' ')[0]}’s inbox` : 'Inbox'}</h1>
        </div>
        {stats && (
          <p className="muted mono" style={{ margin: 0, fontSize: '0.85rem' }}>
            {stats.library} in library · {stats.archived} archived · {stats.tags} tags
          </p>
        )}
      </div>

      <AddBar initialUrl={params.get('add') ?? ''} />

      {isLoading && <Skeleton lines={4} />}
      {error && <ErrorNotice error={error} retry={() => refetch()} />}
      {data && data.items.length === 0 && (
        <Empty title="Inbox zero">
          Everything you save lands here first. Keep what’s worth returning to; archive the rest.
        </Empty>
      )}
      {data && data.items.length > 0 && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            {data.total} waiting to be filed. <b>Keep</b> moves an item to your library; <b>Archive</b> keeps it searchable but out of the way.
          </p>
          <div className="cards">
            {data.items.map((item) => (
              <IndexCard key={item.id} item={item} mode="inbox" />
            ))}
          </div>
        </>
      )}
    </>
  );
}
