import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useAsk, useAskHistory, useMeta, useTags } from '../api/hooks';
import type { Answer } from '../api/types';
import { useFeedback } from '../components/feedback';
import { Empty, Spinner } from '../components/ui';
import { splitCitations, timeAgo } from '../lib/format';

export function AskPage() {
  const [params] = useSearchParams();
  const about = params.get('about');
  const { data: meta } = useMeta();
  const { data: tags } = useTags();
  const { data: history } = useAskHistory();
  const { ask, forget } = useAsk();
  const { toast } = useFeedback();
  const [question, setQuestion] = useState(params.get('q') ?? (about ? `What are the key ideas in "${about}"?` : ''));
  const [tag, setTag] = useState('');
  const [shown, setShown] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (question.trim().length < 3) return setError('Ask a question of at least a few words');
    setError(null);
    try {
      setShown(await ask.mutateAsync({ question: question.trim(), tag: tag || undefined }));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)' }}>
      <div>
        <div className="page-head">
          <div>
            <div className="eyebrow">Reference desk</div>
            <h1>Ask your library</h1>
          </div>
        </div>
        <form className="ask-form" onSubmit={submit}>
          <input className="input" aria-label="Your question" placeholder="What did I save about…?" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} />
          <select className="select" style={{ width: 'auto' }} aria-label="Limit to tag" value={tag} onChange={(e) => setTag(e.target.value)}>
            <option value="">Whole library</option>
            {tags?.map((t) => (
              <option key={t.id} value={t.name}>
                Tag: {t.name}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" disabled={ask.isPending}>
            {ask.isPending && <Spinner label="Thinking" />}
            {ask.isPending ? 'Searching…' : 'Ask'}
          </button>
        </form>
        <p className="muted" style={{ fontSize: '0.85rem' }}>
          {meta?.ai_enabled
            ? `Claude (${meta.ai_model}) answers only from passages in your library and cites them.`
            : 'Claude isn’t configured, so you’ll get the most relevant passages instead of a written answer.'}
        </p>
        {error && <div className="notice error" role="alert">{error}</div>}
        {shown ? <AnswerView answer={shown} /> : (
          <Empty title="Ask anything you’ve saved">
            For example: “What helps memory consolidation?” or “Which newsletters mentioned interest rates?”
          </Empty>
        )}
      </div>

      <aside className="panel" style={{ marginTop: 6 }} aria-label="Previous questions">
        <h2>Previous questions</h2>
        {!history?.length && <p className="muted" style={{ fontSize: '0.88rem', margin: 0 }}>Your questions will appear here.</p>}
        <ul className="history">
          {history?.map((h) => (
            <li key={h.id}>
              <button className="q" onClick={() => setShown(h)}>
                {h.question}
                <span className="muted" style={{ display: 'block', fontSize: '0.75rem' }}>{timeAgo(h.created_at)} · {h.source === 'ai' ? 'answered' : 'passages'}</span>
              </button>
              <button
                className="btn btn-ghost btn-sm"
                aria-label={`Forget “${h.question}”`}
                onClick={() => forget.mutate(h.id, { onSuccess: () => { if (shown?.id === h.id) setShown(null); }, onError: (e) => toast({ title: 'Could not delete', body: errorMessage(e), tone: 'error' }) })}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

export function AnswerView({ answer }: { answer: Answer }) {
  const byN = new Map(answer.citations.map((c) => [c.n, c]));
  return (
    <section className="answer" aria-label="Answer">
      <div className="answer-q">{answer.question}</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <span className={`source-pill ${answer.source === 'ai' ? 'ai' : 'plain'}`}>
          {answer.source === 'ai' ? `✦ Answered by Claude · ${answer.model}` : 'No AI answer · retrieved passages'}
        </span>
        {answer.confidence && <span className="source-pill plain">confidence: {answer.confidence}</span>}
      </div>
      {answer.note && <div className="notice">{answer.note}</div>}
      <div className="answer-text">
        {splitCitations(answer.answer).map((part, i) =>
          typeof part === 'number' ? (
            byN.has(part) ? (
              <a key={i} className="cite" href={`#source-${answer.id}-${part}`} aria-label={`Source ${part}`}>
                {part}
              </a>
            ) : null
          ) : (
            <span key={i}>{part}</span>
          ),
        )}
      </div>
      {answer.citations.length > 0 && (
        <div className="sources">
          {answer.citations.map((c) => (
            <div className="source" key={c.n} id={`source-${answer.id}-${c.n}`}>
              <div className="source-head">
                <span className="cite">{c.n}</span>
                <Link to={`/items/${c.item_id}`} style={{ fontWeight: 700 }}>
                  {c.title}
                </Link>
              </div>
              <p className="source-excerpt">{c.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
