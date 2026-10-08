import {useState} from "react";
import Modal from "./Modal";
import Button from "./Button";

export default function ConfirmRecycleAction({title, permanent = false, busy, error, onClose, onConfirm}) {
  const [confirmation, setConfirmation] = useState("");
  return <Modal title={permanent ? "Confirm permanent deletion" : "Move simulation to recycle bin"}
    onClose={onClose} canDismiss={!busy}>
    <p>{title}</p>
    <p>{permanent ? "The run and all associated execution evidence will be permanently deleted and cannot be recovered. Shared uploads remain available to other runs."
      : "The simulation will leave active history. Its task, uploads, and execution evidence will be preserved and can be restored."}</p>
    {permanent && <label>Type DELETE to confirm<input autoComplete="off" value={confirmation} onChange={event => setConfirmation(event.target.value)} disabled={busy}/></label>}
    {error && <p role="alert">{error}</p>}
    <Button onClick={onClose} disabled={busy}>Cancel</Button>{" "}
    <Button variant="danger" onClick={onConfirm} disabled={busy || (permanent && confirmation !== "DELETE")}>
      {busy ? "Saving…" : permanent ? "Delete permanently" : "Move to bin"}
    </Button>
  </Modal>;
}
