import {useEffect, useRef, useState} from "react";
import {workspaceClient} from "../../services/workspaceClient";
import {organizationFeedback} from "../../utils/organizationFeedback";
import Modal from "../common/Modal";
export default function OrganizationInvites({workspace, initialCode = "", onChanged}) {
  const allowed=workspace?.kind === "organization" && ["owner","admin"].includes(workspace.membershipRole);
  const [invites,setInvites]=useState([]),[code,setCode]=useState(initialCode),[codeId,setCodeId]=useState("");
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [confirmation,setConfirmation]=useState(null);
  const [historyReady,setHistoryReady]=useState(false);
  const alive=useRef(false),locked=useRef(false),version=useRef(0);
  useEffect(()=>{
    alive.current=true;const generation=++version.current;
    if(initialCode)setCode(initialCode);
    setLoading(true);setHistoryReady(false);setInvites([]);setError("");
    if(allowed) workspaceClient.listInvites(workspace.id).then(data=>{
      if(alive.current&&generation===version.current){setInvites(data.invites);setHistoryReady(true);if(initialCode)setCodeId(data.invites.find(i=>i.status === "active")?.id ?? "");}
    }).catch(err=>{if(alive.current&&generation===version.current)setError(organizationFeedback(err,"invite"));})
      .finally(()=>{if(alive.current&&generation===version.current)setLoading(false);});
    else {setCode("");setLoading(false);}
    const lifecycleVersion=version;
    return()=>{alive.current=false;++lifecycleVersion.current;};
  },[allowed,workspace?.id,initialCode]);
  if(!allowed) return workspace?.kind === "organization" ? <section className="organization-section"><h2>Invite a teammate</h2><p>An Owner or Admin of {workspace.name} can generate an invitation. Your Member role cannot manage invitation codes.</p></section> : null;
  async function change(invite) {
    if(locked.current||!historyReady)return;locked.current=true;const generation=++version.current;setBusy(true);setError("");
    try {
      const data=await(invite ? workspaceClient.revokeInvite(workspace.id,invite.id) : workspaceClient.generateInvite(workspace.id));
      if(!alive.current||generation!==version.current)return;
      setInvites(data.invites);setHistoryReady(true);setCode(data.joinCode ?? "");setCodeId(data.invites.find(i=>i.status === "active")?.id ?? "");setConfirmation(null);
      setNotice(invite ? "Invitation revoked. It can no longer be used." : "New invitation saved. Copy it now; it will not be shown after you leave this workspace.");onChanged?.();
    } catch(err){if(alive.current){setHistoryReady(false);setCode("");setConfirmation(null);setError(organizationFeedback(err,"invite"));}}
    finally {locked.current=false;if(alive.current)setBusy(false);}
  }
  async function refresh() {
    if(locked.current)return;locked.current=true;const generation=++version.current;setBusy(true);setHistoryReady(false);setError("");
    try {const data=await workspaceClient.listInvites(workspace.id);if(!alive.current||generation!==version.current)return;
      setInvites(data.invites);setHistoryReady(true);if(data.invites.find(i=>i.status === "active")?.id!==codeId)setCode("");setNotice("Invitation history refreshed.");
    } catch(err){if(alive.current)setError(organizationFeedback(err,"invite"));}
    finally{locked.current=false;if(alive.current)setBusy(false);}
  }
  async function copy(){try{await navigator.clipboard.writeText(code);setNotice("Invitation copied. Share it privately with one person.");}catch{setError("Select the code and copy it manually; clipboard access is unavailable.");}}
  const active=invites.find(i=>i.status === "active");
  return <section className="organization-section" aria-label="Organization invitations"><h2>Invite a teammate to {workspace.name}</h2>
    <p>Each code can be used once. <strong>No timed expiry is configured:</strong> it stays valid until used, revoked or replaced. Pending invitations are unused codes, not emailed requests.</p>
    <button className="organization-primary-button" disabled={busy||loading||!historyReady} onClick={()=>active ? setConfirmation({type:"replace"}) : change()}>{active ? "Replace invitation" : "Create invitation"}</button>{" "}
    <button className="organization-secondary-button" disabled={busy||loading} onClick={refresh}>Refresh invitations</button>
    {code && <div className="organization-created"><div><label>New one-time code<input readOnly value={code} autoComplete="off"/></label>
      <button className="organization-secondary-button" onClick={copy}>Copy invite code</button>{" "}<button className="organization-secondary-button" onClick={()=>{setCode("");onChanged?.();}}>Hide code</button>
      <p>Copy and share privately now. Once hidden or closed, the code cannot be retrieved. Generate a replacement if needed.</p></div></div>}
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{loading&&<p role="status">Loading invitation history…</p>}
    {!loading&&!historyReady&&<p>Invitation history is unavailable. Refresh invitations before changing any codes.</p>}
    {historyReady&&!invites.length&&<p>No invitations yet. Create one to invite your first teammate.</p>}
    <ul className="invitation-history">{invites.map((invite,index)=><li key={invite.id}><strong>Invitation {index+1} · {invite.status === "active" ? "Ready to use once" : invite.status === "consumed" ? "Already used" : "Revoked"}</strong>
      <p>Created {new Date(invite.createdAt).toLocaleString()}{invite.usedAt ? ` · Used ${new Date(invite.usedAt).toLocaleString()}` : ""}. The secret is never shown in history.</p>
      {invite.status === "active"&&<button className="organization-secondary-button" disabled={busy||!historyReady} onClick={()=>setConfirmation({type:"revoke",invite})}>Revoke invitation</button>}
      <details><summary>Audit details</summary><p>Created by {invite.createdByUserId}.{invite.usedByUserId&&` Used by ${invite.usedByUserId}.`}</p></details></li>)}</ul>
    {confirmation&&<Modal title={confirmation.type === "replace" ? "Replace invitation" : "Revoke invitation"} onClose={()=>setConfirmation(null)} canDismiss={!busy}>
      <p>{confirmation.type === "replace" ? "The current unused code will stop working. A new code will be shown once for you to copy." : "This unused code will stop working. You can create a new invitation later."}</p>
      {error&&<p role="alert">{error}</p>}<button className="organization-primary-button" disabled={busy||!historyReady} onClick={()=>change(confirmation.invite)}>{busy ? "Saving…" : "Confirm"}</button></Modal>}
  </section>;
}
