import { useEffect, useId, useRef, type ReactNode } from 'react';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  className?: string;
  children: ReactNode;
}

/** Native <dialog>: focus trapping, Esc and the backdrop come from the browser. */
export function Dialog({ open, onClose, title, className = '', children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`dialog ${className}`}
      aria-labelledby={title ? titleId : undefined}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onMouseDown={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <>
          {title && (
            <div className="dialog-head">
              <h2 id={titleId}>{title}</h2>
            </div>
          )}
          {children}
        </>
      )}
    </dialog>
  );
}
