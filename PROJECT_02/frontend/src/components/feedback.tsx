import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { Dialog } from './Dialog';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastInput {
  title: string;
  body?: string;
  tone?: 'success' | 'error' | 'reminder';
  actions?: ToastAction[];
  /** Keep on screen until acted on (reminders). */
  sticky?: boolean;
  id?: string;
}

interface ToastItem extends ToastInput {
  id: string;
}

interface ConfirmOptions {
  title: string;
  body?: string;
  confirmLabel?: string;
  danger?: boolean;
}

interface FeedbackApi {
  toast: (t: ToastInput) => string;
  dismissToast: (id: string) => void;
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
}

const FeedbackContext = createContext<FeedbackApi | null>(null);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [pending, setPending] = useState<(ConfirmOptions & { resolve: (ok: boolean) => void }) | null>(null);
  const counter = useRef(0);

  const dismissToast = useCallback((id: string) => setToasts((all) => all.filter((t) => t.id !== id)), []);

  const toast = useCallback(
    (input: ToastInput) => {
      const id = input.id ?? `t${++counter.current}`;
      setToasts((all) => [...all.filter((t) => t.id !== id), { ...input, id }].slice(-5));
      if (!input.sticky) window.setTimeout(() => dismissToast(id), input.tone === 'error' ? 7000 : 4000);
      return id;
    },
    [dismissToast],
  );

  const confirm = useCallback(
    (opts: ConfirmOptions) => new Promise<boolean>((resolve) => setPending({ ...opts, resolve })),
    [],
  );

  const settle = (ok: boolean) => {
    pending?.resolve(ok);
    setPending(null);
  };

  const api = useMemo(() => ({ toast, dismissToast, confirm }), [toast, dismissToast, confirm]);

  return (
    <FeedbackContext.Provider value={api}>
      {children}
      <div className="toasts" role="region" aria-label="Notifications" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone ?? 'success'}`} role={t.tone === 'error' ? 'alert' : 'status'}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="toast-title">{t.title}</div>
              {t.body && <div className="toast-body">{t.body}</div>}
              {t.actions && (
                <div className="toast-actions">
                  {t.actions.map((a) => (
                    <button
                      key={a.label}
                      className="btn btn-sm"
                      onClick={() => {
                        a.onClick();
                        dismissToast(t.id);
                      }}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button className="toast-close" aria-label="Dismiss notification" onClick={() => dismissToast(t.id)}>
              ×
            </button>
          </div>
        ))}
      </div>
      <Dialog open={pending !== null} onClose={() => settle(false)} title={pending?.title}>
        <div className="dialog-body">
          {pending?.body && <p style={{ marginTop: 0 }}>{pending.body}</p>}
          <div className="form-actions">
            <button className="btn btn-ghost" onClick={() => settle(false)}>
              Cancel
            </button>
            <button className={`btn ${pending?.danger ? 'btn-danger' : 'btn-primary'}`} onClick={() => settle(true)} autoFocus>
              {pending?.confirmLabel ?? 'Confirm'}
            </button>
          </div>
        </div>
      </Dialog>
    </FeedbackContext.Provider>
  );
}

export function useFeedback(): FeedbackApi {
  const ctx = useContext(FeedbackContext);
  if (!ctx) throw new Error('useFeedback must be used inside <FeedbackProvider>');
  return ctx;
}
