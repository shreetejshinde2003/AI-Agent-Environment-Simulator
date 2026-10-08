import {useEffect, useState} from "react";
import {workspaceClient} from "../../services/workspaceClient";

export default function OrganizationInvites({workspace, initialCode = "", onChanged}) {
  const allowed = workspace?.kind === "organization" && ["owner", "admin"].includes(workspace.membershipRole);
  const [invites, setInvites] = useState([]), [code, setCode] = useState(initialCode);
  const [codeId, setCodeId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  useEffect(() => {
    let cancelled = false;
    if (allowed) workspaceClient.listInvites(workspace.id).then(data => {if (!cancelled) {setInvites(data.invites); if (initialCode) setCodeId(data.invites.find(item => item.status === "active")?.id ?? "");}})
      .catch(err => {if (!cancelled) setError(err.message);})
      .finally(() => {if (!cancelled) setLoading(false);});
    if (!allowed) {setInvites([]); setCode("");}
    return () => {cancelled = true;};
  }, [allowed, workspace?.id, initialCode]);
  if (!allowed) return null;
  async function change(invite) {
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await (invite ? workspaceClient.revokeInvite(workspace.id, invite.id) : workspaceClient.generateInvite(workspace.id));
      setInvites(data.invites); setCode(data.joinCode ?? ""); setCodeId(data.invites.find(item => item.status === "active")?.id ?? ""); onChanged?.();
    } catch (err) {setError(err.message);} finally {setBusy(false);}
  }
  async function refresh() {
    setBusy(true); setError("");
    try {
      const data = await workspaceClient.listInvites(workspace.id);
      setInvites(data.invites);
      if (data.invites.find(item => item.status === "active")?.id !== codeId) setCode("");
      setNotice("Invitation history refreshed.");
    } catch (err) {setError(err.message);} finally {setBusy(false);}
  }
  async function copy() {
    try {await navigator.clipboard.writeText(code); setNotice("Invite copied.");}
    catch {setError("Copy unavailable. Select and copy the code below.");}
  }
  return <section className="organization-section" aria-label="Organization invitations">
    <h2>Organization invitations</h2><p>Codes admit one person. Generating a replacement revokes the current unused code. Only Owners and Admins manage invitations.</p>
    <button disabled={busy || loading} onClick={refresh}>Refresh invitations</button>{" "}
    <button disabled={busy || loading} onClick={() => change()}>Generate replacement invite</button>
    {code && <div><label>New one-time code<input readOnly value={code}/></label><button onClick={copy}>Copy invite code</button><p>Save this secret now. We store only its hash; you can always generate a replacement here.</p></div>}
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading && <p role="status">Loading invitation history…</p>}
    {!loading && !invites.length && <p>No invitations yet.</p>}
    <ul>{invites.map(invite => <li key={invite.id}><strong>Masked code •••• · {invite.status}</strong><p>Created {new Date(invite.createdAt).toLocaleString()} by {invite.createdByUserId}. {invite.usedAt ? `Used by ${invite.usedByUserId} on ${new Date(invite.usedAt).toLocaleString()}` : "Unused"}</p>{invite.status === "active" && <button disabled={busy} onClick={() => change(invite)}>Revoke unused invite</button>}</li>)}</ul>
  </section>;
}
