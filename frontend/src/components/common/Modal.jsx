import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import "./Modal.css";

/** Native modal dialog keeps the rest of the app inert and contains Tab focus. */
export default function Modal({ title, onClose, canDismiss = true, className = "", returnFocusRef, children }) {
  const dialogRef = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    const returnTo = document.activeElement;
    // This ref contains a requested selector, not a DOM node. Its latest value
    // intentionally distinguishes successful creation from cancellation.
    const focusDestination = returnFocusRef;
    dialog.showModal();
    (dialog.querySelector("[autofocus]") || dialog.querySelector("textarea, input:not([type=hidden]), select") || dialog.querySelector("button"))?.focus();

    return () => {
      dialog.close();
      // The creation flow may navigate away and remove its trigger.
      requestAnimationFrame(() => {
        if (dialog.open) return; // Strict Mode may have reopened this dialog.
        const requested = focusDestination?.current;
        const destination = requested && document.querySelector(requested);
        if (destination) destination.focus();
        else if (returnTo?.isConnected) returnTo.focus();
        else document.querySelector("main")?.focus();
      });
    };
  }, [returnFocusRef]);

  function containTab(event) {
    if (event.key !== "Tab") return;
    const dialog = dialogRef.current;
    const controls = [...dialog.querySelectorAll('button, input, textarea, select, summary, a[href], [tabindex="0"]')]
      .filter(control => !control.matches(":disabled") && control.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (!first) { event.preventDefault(); dialog.focus(); }
    else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  }

  return createPortal(
    <dialog ref={dialogRef} className={`modal-dialog ${className}`} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} onKeyDown={containTab}
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
