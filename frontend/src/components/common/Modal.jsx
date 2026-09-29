import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import "./Modal.css";

/** Native modal dialog keeps the rest of the app inert and contains Tab focus. */
export default function Modal({ title, onClose, canDismiss = true, children }) {
  const dialogRef = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    const returnTo = document.activeElement;
    dialog.showModal();
    (dialog.querySelector("[autofocus]") || dialog.querySelector("textarea, input:not([type=hidden]), select") || dialog.querySelector("button"))?.focus();

    return () => {
      dialog.close();
      // The creation flow may navigate away and remove its trigger.
      requestAnimationFrame(() => {
        if (dialog.open) return; // Strict Mode may have reopened this dialog.
        if (returnTo?.isConnected) returnTo.focus();
        else document.querySelector("main")?.focus();
      });
    };
  }, []);

  return createPortal(
    <dialog ref={dialogRef} className="modal-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}
      onCancel={event => { event.preventDefault(); if (canDismiss) onClose(); }}>
      <div className="modal-panel">
        <div className="modal-header">
          <h3 id={titleId}>{title}</h3>
          <button type="button" className="modal-close-btn" onClick={onClose}
            disabled={!canDismiss} aria-label={`Close ${title}`}>
            <X size={16} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </dialog>, document.body,
  );
}
