import { useEffect } from "react";
import { X } from "lucide-react";
import "./Modal.css";

/**
 * Modal — minimal overlay dialog. Closes on backdrop click or Escape.
 * Used by CreateTaskModal / AddAgentModal (components/dashboard/) —
 * kept generic here so any future form can reuse it.
 */
export default function Modal({ title, onClose, children }) {
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
            <X size={16} strokeWidth={2} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
