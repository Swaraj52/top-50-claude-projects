import { useRef, useState, type DragEvent, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useSave } from '../api/hooks';
import type { SaveResult } from '../api/types';
import { looksLikeUrl, parseTags } from '../lib/format';
import { useFeedback } from './feedback';
import { Spinner } from './ui';

type Mode = 'link' | 'text' | 'file';
const ACCEPT = '.txt,.md,.markdown,.html,.htm,.eml,.pdf';

export function AddBar({ initialUrl = '' }: { initialUrl?: string }) {
  const save = useSave();
  const navigate = useNavigate();
  const { toast } = useFeedback();
  const [mode, setMode] = useState<Mode>('link');
  const [url, setUrl] = useState(initialUrl);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [kind, setKind] = useState<'note' | 'newsletter'>('note');
  const [tags, setTags] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const busy = save.url.isPending || save.text.isPending || save.file.isPending;

  function saved(r: SaveResult) {
    setError(null);
    const dup = r.warnings.includes('You already saved this link.');
    toast({
      title: dup ? 'Already in your library' : 'Saved to inbox',
      body: [r.item.title, ...r.warnings.filter((w) => !w.startsWith('You already'))].join(' · '),
      tone: r.warnings.length && !dup ? 'reminder' : 'success',
      actions: [{ label: 'Open', onClick: () => navigate(`/items/${r.item.id}`) }],
    });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (mode === 'link') {
        if (!looksLikeUrl(url)) return setError('Paste a full web address, e.g. https://example.com/article');
        saved(await save.url.mutateAsync({ url: url.trim(), tags: parseTags(tags) }));
        setUrl('');
      } else if (mode === 'text') {
        if (!text.trim()) return setError('Paste some text first');
        saved(await save.text.mutateAsync({ title: title.trim(), content: text, kind, tags: parseTags(tags) }));
        setText('');
        setTitle('');
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function upload(file: File) {
    setError(null);
    const form = new FormData();
    form.append('file', file);
    form.append('tags', tags);
    try {
      saved(await save.file.mutateAsync(form));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) upload(file);
  }

  return (
    <form className="addbar" onSubmit={submit} aria-label="Add to library">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <div className="seg" role="tablist" aria-label="What to add">
          {(['link', 'text', 'file'] as Mode[]).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => { setMode(m); setError(null); }}>
              {m === 'link' ? 'Link or video' : m === 'text' ? 'Paste text' : 'Upload file'}
            </button>
          ))}
        </div>
        <input className="input" style={{ maxWidth: 260 }} placeholder="Tags, comma separated" aria-label="Tags" value={tags} onChange={(e) => setTags(e.target.value)} />
      </div>

      {mode === 'link' && (
        <div className="addbar-row">
          <input
            className="input"
            placeholder="Paste an article, newsletter web page or YouTube link…"
            aria-label="Link to save"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            inputMode="url"
            autoFocus={!!initialUrl}
          />
          <button className="btn btn-primary" disabled={busy || !url.trim()}>
            {busy ? <Spinner label="Saving" /> : null}
            {busy ? 'Reading the page…' : 'Save'}
          </button>
        </div>
      )}

      {mode === 'text' && (
        <div style={{ display: 'grid', gap: 10 }}>
          <div className="addbar-row">
            <input className="input" placeholder="Title (optional)" aria-label="Title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} />
            <div className="seg" role="group" aria-label="Type">
              <button type="button" aria-pressed={kind === 'note'} onClick={() => setKind('note')}>Note</button>
              <button type="button" aria-pressed={kind === 'newsletter'} onClick={() => setKind('newsletter')}>Newsletter</button>
            </div>
          </div>
          <textarea className="textarea" placeholder="Paste a newsletter, an email, meeting notes, a transcript…" aria-label="Text to save" value={text} onChange={(e) => setText(e.target.value)} />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" disabled={busy || !text.trim()}>
              {busy ? 'Saving…' : 'Save text'}
            </button>
          </div>
        </div>
      )}

      {mode === 'file' && (
        <div
          className={`dropzone ${over ? 'over' : ''}`}
          role="button"
          tabIndex={0}
          aria-label="Choose a file to upload"
          onClick={() => fileInput.current?.click()}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileInput.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
        >
          {busy ? 'Reading the file…' : <>Drop a file here or <u>browse</u>: PDF, newsletter .eml, .md, .txt or .html (max 10 MB)</>}
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
              e.target.value = '';
            }}
          />
        </div>
      )}

      {error && (
        <p className="field-error" role="alert" style={{ marginBottom: 0 }}>
          {error}
        </p>
      )}
      {mode === 'link' && !error && (
        <p className="addbar-hint" style={{ marginBottom: 0 }}>
          Articles are saved as clean text; YouTube links also save the transcript when YouTube provides one.
        </p>
      )}
    </form>
  );
}
