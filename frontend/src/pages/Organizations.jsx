import { useState } from "react";
import {
  Building2,
  KeyRound,
  Plus,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { workspaceClient } from "../services/workspaceClient";
import { useWorkspace } from "../hooks/useWorkspace";
import {
  JOIN_CODE_MAX,
  ORGANIZATION_NAME_MAX,
  joinCodeError,
  organizationNameError,
} from "../utils/organizationValidation";
import "./Organizations.css";

function WorkspaceCard({ workspace, personal = false }) {
  return (
    <article className="organization-workspace-card">
      <div className="organization-workspace-icon" aria-hidden="true">
        {personal ? <UserRound size={18} /> : <Building2 size={18} />}
      </div>
      <div>
        <strong>{workspace.name}</strong>
        <p>
          {personal
            ? "Private workspace created for your account."
            : `${workspace.membershipRole === "owner" ? "Owner" : "Member"} · Private organization workspace`}
        </p>
      </div>
    </article>
  );
}

export default function Organizations() {
  const {
    workspaceData,
    activeWorkspace,
    status: loadState,
    error: loadError,
    refreshWorkspaces,
  } = useWorkspace();
  const [organizationName, setOrganizationName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [action, setAction] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [createdOrganization, setCreatedOrganization] = useState(null);
  const [notice, setNotice] = useState(null);


  async function handleCreate(event) {
    event.preventDefault();
    const validation = organizationNameError(organizationName);
    if (validation) {
      setActionError(validation);
      return;
    }

    setAction("create");
    setActionError(null);
    setNotice(null);
    setCreatedOrganization(null);
    try {
      const created = await workspaceClient.createOrganization(
        organizationName.trim(),
      );
      setCreatedOrganization(created);
      setOrganizationName("");
      await refreshWorkspaces(created.id);
    } catch (error) {
      setActionError(error.message || "Unable to create organization.");
    } finally {
      setAction(null);
    }
  }

  async function handleJoin(event) {
    event.preventDefault();
    const validation = joinCodeError(joinCode);
    if (validation) {
      setActionError(validation);
      return;
    }

    setAction("join");
    setActionError(null);
    setNotice(null);
    setCreatedOrganization(null);
    try {
      const joined = await workspaceClient.joinOrganization(joinCode.trim());
      setJoinCode("");
      setNotice(`Joined ${joined.name} as ${joined.membershipRole}.`);
      await refreshWorkspaces(joined.id);
    } catch (error) {
      setActionError(error.message || "Unable to join organization.");
    } finally {
      setAction(null);
    }
  }

  const busy = action !== null;
  const organizations = workspaceData?.organizations ?? [];

  return (
    <div className="organizations-page">
      <header className="organizations-heading">
        <p className="organizations-eyebrow">Workspace access</p>
        <h1>Organizations</h1>
        <p>
          Your Personal Workspace is private. Join an organization only with a
          code shared directly with you, or create a new private organization.
        </p>
      </header>

      {actionError && (
        <div className="organization-alert is-error" role="alert">
          {actionError}
        </div>
      )}

      {notice && (
        <div className="organization-alert is-success" role="status">
          {notice}
        </div>
      )}

      {createdOrganization && (
        <section className="organization-created" aria-labelledby="organization-created-title">
          <ShieldCheck size={20} aria-hidden="true" />
          <div>
            <h2 id="organization-created-title">
              {createdOrganization.name} created
            </h2>
            <p>
              Share this join code only with people you intend to invite. The
              application does not provide a public organization directory.
            </p>
            <code>{createdOrganization.joinCode}</code>
            <p className="organization-created-note">
              Save the code now. The stored organization record does not expose
              the original plaintext code later.
            </p>
          </div>
        </section>
      )}

      <section className="organization-section" aria-labelledby="your-workspaces-title">
        <div className="organization-section-heading">
          <div>
            <h2 id="your-workspaces-title">Your workspaces</h2>
            <p>Only workspaces available to your authenticated account are listed.</p>
          </div>
          {loadState === "error" && (
            <button type="button" className="organization-secondary-button" onClick={() => refreshWorkspaces().catch(() => {})}>
              Retry
            </button>
          )}
        </div>

        {loadState === "loading" && (
          <p className="organization-state" role="status">Loading your workspaces…</p>
        )}

        {loadState === "error" && (
          <p className="organization-state is-error" role="alert">
            Unable to load your workspace memberships. {loadError?.message}
          </p>
        )}

        {loadState === "ready" && workspaceData && (
          <div className="organization-workspace-list">
            <WorkspaceCard workspace={workspaceData.personalWorkspace} personal />
            {organizations.map(workspace => (
              <WorkspaceCard key={workspace.id} workspace={workspace} />
            ))}
          </div>
        )}
      </section>

      <div className="organization-actions-grid">
        <section className="organization-action-card" aria-labelledby="create-organization-title">
          <div className="organization-action-icon" aria-hidden="true">
            <Plus size={19} />
          </div>
          <h2 id="create-organization-title">Create Organization</h2>
          <p>Create a private organization and become its owner.</p>

          <form onSubmit={handleCreate}>
            <label htmlFor="organization-name">Organization name</label>
            <input
              id="organization-name"
              value={organizationName}
              maxLength={ORGANIZATION_NAME_MAX}
              disabled={busy}
              autoComplete="organization"
              onChange={event => setOrganizationName(event.target.value)}
              placeholder="Example: IICT"
            />
            <button
              type="submit"
              className="organization-primary-button"
              disabled={busy || !!organizationNameError(organizationName)}
            >
              {action === "create" ? "Creating…" : "Create organization"}
            </button>
          </form>
        </section>

        <section className="organization-action-card" aria-labelledby="join-organization-title">
          <div className="organization-action-icon" aria-hidden="true">
            <KeyRound size={19} />
          </div>
          <h2 id="join-organization-title">Join Organization</h2>
          <p>Use a private code provided directly by an organization owner.</p>

          <form onSubmit={handleJoin}>
            <label htmlFor="organization-join-code">Join code</label>
            <input
              id="organization-join-code"
              value={joinCode}
              maxLength={JOIN_CODE_MAX}
              disabled={busy}
              autoComplete="off"
              spellCheck="false"
              onChange={event => setJoinCode(event.target.value)}
              placeholder="XXXX-XXXX-XXXX"
            />
            <button
              type="submit"
              className="organization-primary-button"
              disabled={busy || !!joinCodeError(joinCode)}
            >
              {action === "join" ? "Joining…" : "Join organization"}
            </button>
          </form>
        </section>
      </div>

      <p className="organization-boundary-note">
        Active workspace: <strong>{activeWorkspace?.name ?? "Resolving…"}</strong>.
        Workspace selection is available now, but existing simulation history is
        not yet partitioned by workspace.
      </p>
    </div>
  );
}
