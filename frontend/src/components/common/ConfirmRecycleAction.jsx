import Modal from "./Modal";
import Button from "./Button";

export default function ConfirmRecycleAction({title, permanent = false, busy, error, onClose, onConfirm}) {
  return <Modal title={permanent ? "Confirm permanent deletion" : "Move simulation to recycle bin"}
    onClose={onClose} canDismiss={!busy}>
    <p>{title}</p>
    <p>{permanent ? "This cannot be undone. Runs with execution evidence cannot be permanently deleted."
      : "The simulation will leave active history. Its task, uploads, and execution evidence will be preserved and can be restored."}</p>
    {error && <p role="alert">{error}</p>}
    <Button onClick={onClose} disabled={busy}>Cancel</Button>{" "}
    <Button variant="danger" onClick={onConfirm} disabled={busy}>
      {busy ? "Saving…" : permanent ? "Delete permanently" : "Move to bin"}
    </Button>
  </Modal>;
}
