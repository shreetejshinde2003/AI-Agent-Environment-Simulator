import { useEffect, useMemo, useState } from "react";
import { Shield, UsersRound } from "lucide-react";

import { workspaceClient } from "../../services/workspaceClient";
import {
  canChangeOrganizationRoles,
  canViewOrganizationMembers,
  organizationRoleLabel,
} from "../../utils/organizationMembers";

function memberName(member) {
  return member.displayName || member.email || "Organization member";
}

export default function OrganizationMembers({ workspace, onMembershipChanged }) {
  const [members, setMembers] = useState([]);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [changingUserId, setChangingUserId] = useState(null);
  const [notice, setNotice] = useState(null);

  const canView =
    workspace?.kind === "organization" &&
    canViewOrganizationMembers(workspace.membershipRole);
  const canChangeRoles = canChangeOrganizationRoles(workspace?.membershipRole);

  useEffect(() => {
    let cancelled = false;

    if (!canView) {
      setMembers([]);
      setStatus("idle");
      setError(null);
      setNotice(null);
      return () => {
        cancelled = true;
      };
    }

    setStatus("loading");
    setError(null);
    setNotice(null);

    workspaceClient
      .listOrganizationMembers(workspace.id)
      .then(result => {
        if (cancelled) return;
        setMembers(result.members ?? []);
        setStatus("ready");
      })
      .catch(nextError => {
        if (cancelled) return;
        setMembers([]);
        setError(nextError);
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [canView, workspace?.id]);

  const sortedMembers = useMemo(
    () => [...members].sort((a, b) => memberName(a).localeCompare(memberName(b))),
    [members],
  );

  async function changeRole(member, membershipRole) {
    if (!canChangeRoles || membershipRole === member.membershipRole) return;

    setChangingUserId(member.userId);
    setError(null);
    setNotice(null);

    try {
      const updated = await workspaceClient.changeOrganizationMemberRole(
        workspace.id,
        member.userId,
        membershipRole,
      );

      setMembers(current =>
        current.map(item =>
          item.userId === updated.userId
            ? { ...item, membershipRole: updated.membershipRole }
            : item,
        ),
      );
      setNotice(`${memberName(member)} is now ${organizationRoleLabel(updated.membershipRole)}.`);
      await onMembershipChanged?.();
    } catch (nextError) {
      setError(nextError);
    } finally {
      setChangingUserId(null);
    }
  }

  if (workspace?.kind !== "organization") {
    return (
      <section className="organization-section" aria-labelledby="member-management-title">
        <div className="organization-section-heading">
          <div>
            <h2 id="member-management-title">Member management</h2>
            <p>Select an organization workspace to manage its members.</p>
          </div>
        </div>
      </section>
    );
  }

  if (!canView) {
    return (
      <section className="organization-section" aria-labelledby="member-management-title">
        <div className="organization-section-heading">
          <div>
            <h2 id="member-management-title">Member management</h2>
            <p>
              You are a Member of <strong>{workspace.name}</strong>. Member administration is
              available only to organization Owners and Admins.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="organization-section" aria-labelledby="member-management-title">
      <div className="organization-section-heading">
        <div>
          <p className="organizations-eyebrow">{workspace.name}</p>
          <h2 id="member-management-title">Member management</h2>
          <p>
            {canChangeRoles
              ? "Owners can assign Owner, Admin, or Member roles. The backend protects the last active owner."
              : "Admins can view organization members. Owner/Admin role assignment remains owner-only."}
          </p>
        </div>
        <div className="organization-role-badge">
          <Shield size={15} aria-hidden="true" />
          {organizationRoleLabel(workspace.membershipRole)}
        </div>
      </div>

      {error && (
        <div className="organization-alert is-error" role="alert">
          {error.message || "Unable to manage organization members."}
        </div>
      )}

      {notice && (
        <div className="organization-alert is-success" role="status">
          {notice}
        </div>
      )}

      {status === "loading" && (
        <p className="organization-state" role="status">Loading organization members…</p>
      )}

      {status === "ready" && sortedMembers.length === 0 && (
        <p className="organization-state">No active organization members were returned.</p>
      )}

      {status === "ready" && sortedMembers.length > 0 && (
        <div className="organization-member-list">
          {sortedMembers.map(member => (
            <article className="organization-member-row" key={member.userId}>
              <div className="organization-member-avatar" aria-hidden="true">
                {member.profilePicture ? (
                  <img src={member.profilePicture} alt="" referrerPolicy="no-referrer" />
                ) : (
                  <UsersRound size={18} />
                )}
              </div>

              <div className="organization-member-identity">
                <strong>{memberName(member)}</strong>
                <span>{member.email}</span>
              </div>

              {canChangeRoles ? (
                <label className="organization-role-control">
                  <select
                    value={member.membershipRole}
                    disabled={changingUserId !== null}
                    onChange={event => changeRole(member, event.target.value)}
                    aria-label={`Role for ${memberName(member)}`}
                  >
                    <option value="owner">Owner</option>
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                  </select>
                </label>
              ) : (
                <span className="organization-role-badge is-static">
                  {organizationRoleLabel(member.membershipRole)}
                </span>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
