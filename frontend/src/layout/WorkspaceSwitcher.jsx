import { Building2, UserRound } from "lucide-react";

export default function WorkspaceSwitcher({
  workspaces = [],
  activeWorkspace,
  status = "loading",
  error,
  onSelect = () => {},
}) {
  const unavailable = status === "error";
  const loading = status === "loading" && !workspaces.length;
  const ActiveIcon = activeWorkspace?.kind === "organization" ? Building2 : UserRound;

  return (
    <section className="workspace-switcher" aria-label="Active workspace">
      <label htmlFor="workspace-switcher-select">Workspace</label>
      <div className="workspace-switcher-control">
        <ActiveIcon size={15} aria-hidden="true" />
        <select
          id="workspace-switcher-select"
          value={activeWorkspace?.id ?? ""}
          disabled={loading || unavailable || !workspaces.length}
          onChange={event => onSelect(event.target.value)}
          aria-describedby="workspace-switcher-detail"
        >
          {loading && <option value="">Loading workspace…</option>}
          {unavailable && <option value="">Workspace unavailable</option>}
          {!loading && !unavailable && workspaces.map(workspace => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name}
            </option>
          ))}
        </select>
      </div>
      <p id="workspace-switcher-detail" role={unavailable ? "alert" : undefined}>
        {unavailable
          ? error?.message ?? "Unable to load workspace access."
          : activeWorkspace?.kind === "organization"
            ? `${activeWorkspace.membershipRole === "owner" ? "Owner" : "Member"} · Organization`
            : activeWorkspace
              ? "Private Personal Workspace"
              : "Resolving workspace…"}
      </p>
    </section>
  );
}
