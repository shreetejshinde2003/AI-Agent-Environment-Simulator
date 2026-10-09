import {useEffect, useRef, useState} from "react";
import {Building2, UserRound} from "lucide-react";
import OrganizationInvites from "../components/organizations/OrganizationInvites";
import OrganizationMembers from "../components/organizations/OrganizationMembers";
import {workspaceClient} from "../services/workspaceClient";
import {useWorkspace} from "../hooks/useWorkspace";
import {JOIN_CODE_MAX, ORGANIZATION_NAME_MAX, joinCodeError, organizationNameError} from "../utils/organizationValidation";
import {organizationFeedback} from "../utils/organizationFeedback";
import "./Organizations.css";

function WorkspaceCard({workspace, personal = false, active, onOpen}) {
  if (!workspace) return null;
  return <article className="organization-workspace-card">
    <div className="organization-workspace-icon" aria-hidden="true">{personal ? <UserRound size={18}/> : <Building2 size={18}/>}</div>
    <div><strong>{workspace.name}</strong><p>{personal ? "Private workspace created for your account." : `${workspace.membershipRole === "owner" ? "Owner" : workspace.membershipRole === "admin" ? "Admin" : "Member"} · Private organization workspace`}</p>
      <button className="organization-secondary-button" disabled={active} onClick={onOpen}>{active ? "Current workspace" : "Open workspace"}</button></div>
  </article>;
}
export default function Organizations() {
  const {workspaceData, activeWorkspace, status:loadState, error:loadError, refreshWorkspaces, selectWorkspace} = useWorkspace();
  const [organizationName,setOrganizationName] = useState(""), [joinCode,setJoinCode] = useState("");
  const [action,setAction] = useState(null), [error,setError] = useState(""), [notice,setNotice] = useState("");
  const [createdOrganization,setCreatedOrganization] = useState(null);
  const locked = useRef(false), alive = useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(()=>{setCreatedOrganization(current=>current?.id === activeWorkspace?.id ? current : null);},[activeWorkspace?.id]);
  async function submit(event, type) {
    event.preventDefault(); if (locked.current) return;
    const invalid = type === "create" ? organizationNameError(organizationName) : joinCodeError(joinCode);
    if (invalid) {setError(invalid);return;}
    locked.current=true;setAction(type);setError("");setNotice("");setCreatedOrganization(null);
    try {
      const saved = await (type === "create" ? workspaceClient.createOrganization(organizationName.trim()) : workspaceClient.joinOrganization(joinCode.trim()));
      if (!alive.current) return;
      if(type === "create") setOrganizationName(""); else setJoinCode("");
      try {await refreshWorkspaces(saved.id);}
      catch {if(alive.current) setNotice(`${saved.name} was saved, but workspace access could not refresh. Reload your workspaces before repeating this action.`);return;}
      if(!alive.current)return;
      setNotice(type === "create" ? `${saved.name} created. You are its Owner. Invite someone below, or assign HR responsibilities to begin hiring.` : `Joined ${saved.name}. Your saved work will appear in this workspace.`);
      if(type === "create") setCreatedOrganization(saved);
    } catch(err) {if(alive.current)setError(organizationFeedback(err,type));}
    finally {locked.current=false;if(alive.current)setAction(null);}
  }
  const busy=action!==null;
  return <div className="organizations-page">
    <header className="organizations-heading"><p className="organizations-eyebrow">Workspace access</p><h1>Organizations</h1>
      <p>Create a shared workspace for your team, or join one with a private invitation. Your Personal Workspace stays private.</p></header>
    {error && <div className="organization-alert is-error" role="alert">{error}</div>}
    {notice && <div className="organization-alert is-success" role="status">{notice}</div>}
    <div className="organization-actions-grid">
      <section className="organization-action-card"><h2>Create Organization</h2><p>Start here if you are setting up a team. You become its Owner; its saved records are separate from other workspaces.</p>
        <form onSubmit={e=>submit(e,"create")}><label htmlFor="organization-name">Organization name</label>
          <input id="organization-name" value={organizationName} maxLength={ORGANIZATION_NAME_MAX} disabled={busy} autoComplete="organization" onChange={e=>setOrganizationName(e.target.value)} placeholder="Example: Campus Research Team"/>
          <button className="organization-primary-button" disabled={busy||!!organizationNameError(organizationName)}>{action === "create" ? "Creating…" : "Create organization"}</button></form></section>
      <section className="organization-action-card"><h2>Join Organization</h2><p>Use a private code provided directly by an organization Owner or Admin. One invitation admits one person.</p>
        <form onSubmit={e=>submit(e,"join")}><label htmlFor="organization-join-code">Invitation code</label>
          <input id="organization-join-code" value={joinCode} maxLength={JOIN_CODE_MAX} disabled={busy} autoComplete="off" spellCheck="false" onChange={e=>setJoinCode(e.target.value)} placeholder="XXXX-XXXX-XXXX"/>
          <button className="organization-primary-button" disabled={busy||!!joinCodeError(joinCode)}>{action === "join" ? "Joining…" : "Join organization"}</button></form></section>
    </div>
    <section className="organization-section"><div className="organization-section-heading"><div><h2>Your workspaces</h2><p>Open an organization to see its invitations and member controls below.</p></div>
      <button className="organization-secondary-button" disabled={busy||loadState === "loading"} onClick={()=>refreshWorkspaces().catch(()=>{})}>Reload workspaces</button></div>
      {loadState === "loading" && <p role="status">Loading your workspaces…</p>}
      {loadState === "error" && <p role="alert">We could not load your memberships. {organizationFeedback(loadError ?? {},"load")}</p>}
      {loadState === "ready" && <div className="organization-workspace-list"><WorkspaceCard personal workspace={workspaceData?.personalWorkspace} active={activeWorkspace?.kind === "personal"} onOpen={()=>selectWorkspace(workspaceData.personalWorkspace.id)}/>
        {(workspaceData?.organizations ?? []).map(w=><WorkspaceCard key={w.id} workspace={w} active={activeWorkspace?.id === w.id} onOpen={()=>selectWorkspace(w.id)}/>)}</div>}
      {loadState === "ready" && !workspaceData?.organizations?.length && <p>No organizations yet. Create one above, or ask your team for an invitation.</p>}
    </section>
    <details className="organization-section"><summary>What can Owners, Admins and Members do?</summary><ul>
      <li><strong>Owner:</strong> manages the team, access roles and permanent removal of eligible runs. The last active Owner cannot be removed or demoted.</li>
      <li><strong>Admin:</strong> helps invite people and manage ordinary Members; cannot change Owner/Admin access.</li>
      <li><strong>Member:</strong> works with the organization's authorized simulations and saved results; asks a manager to change membership.</li></ul>
      <p>Hiring responsibilities are separate. Being Owner or Admin does not make you a Recruiter, Reviewer or Approver. Assign these explicitly in member management.</p></details>
    <OrganizationInvites key={`invites:${activeWorkspace?.id}`} workspace={activeWorkspace} initialCode={createdOrganization?.id === activeWorkspace?.id ? createdOrganization.joinCode : ""} onChanged={()=>setCreatedOrganization(null)}/>
    <OrganizationMembers key={`members:${activeWorkspace?.id}`} workspace={activeWorkspace} onMembershipChanged={()=>refreshWorkspaces(activeWorkspace?.id)}/>
    <p className="organization-boundary-note">Active workspace: <strong>{activeWorkspace?.name ?? "Loading…"}</strong>. Simulation history and new runs are scoped to this active workspace.</p>
  </div>;
}
