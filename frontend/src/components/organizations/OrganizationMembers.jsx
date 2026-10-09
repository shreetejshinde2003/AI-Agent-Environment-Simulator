import { useEffect, useMemo, useRef, useState } from "react";
import Modal from "../common/Modal";
import { Shield, UsersRound } from "lucide-react";

import { workspaceClient } from "../../services/workspaceClient";
import {
  canManageHrHumanRoles,
  HR_HUMAN_ROLE_OPTIONS,
  humanRoleLabel,
  humanRolesByUser,
} from "../../utils/hrHumanRoles";
import {
  canChangeOrganizationRoles,
  canRemoveOrganizationMember,
  canViewOrganizationMembers,
  organizationRoleLabel,
  isLastOrganizationOwner,
} from "../../utils/organizationMembers";

function memberName(member) {
  return member.displayName || member.email || "Organization member";
}

export default function OrganizationMembers({ workspace, onMembershipChanged }) {
  const alive=useRef(false);
  const [pendingRole,setPendingRole]=useState(null);
  const [pendingRemoval, setPendingRemoval] = useState(null);
  const [members, setMembers] = useState([]);
  const [humanRoleAssignments, setHumanRoleAssignments] = useState([]);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [changingUserId, setChangingUserId] = useState(null);
  const [removingUserId, setRemovingUserId] = useState(null);
  const [changingHumanRole, setChangingHumanRole] = useState(null);
  const [notice, setNotice] = useState(null);
  const [reload,setReload]=useState(0);

  const canView =
    workspace?.kind === "organization" &&
    canViewOrganizationMembers(workspace.membershipRole);
  const canChangeRoles = canChangeOrganizationRoles(workspace?.membershipRole);
  const canManageHumanRoles = canManageHrHumanRoles(workspace?.membershipRole);

  useEffect(() => {
    let cancelled = false;alive.current=true;

    if (!canView) {
      setMembers([]);
      setHumanRoleAssignments([]);
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

    Promise.all([
      workspaceClient.listOrganizationMembers(workspace.id),
      workspaceClient.listOrganizationHumanRoles(workspace.id),
    ])
      .then(([memberResult, roleResult]) => {
        if (cancelled) return;
        setMembers(memberResult.members ?? []);
        setHumanRoleAssignments(roleResult.assignments ?? []);
        setStatus("ready");
      })
      .catch(nextError => {
        if (cancelled) return;
        setMembers([]);
        setHumanRoleAssignments([]);
        setError(nextError);
        setStatus("error");
      });

    return () => {
      cancelled = true;alive.current=false;
    };
  }, [canView, workspace?.id,reload]);

  const sortedMembers = useMemo(
    () => [...members].sort((a, b) => memberName(a).localeCompare(memberName(b))),
    [members],
  );
  const rolesByUser = useMemo(
    () => humanRolesByUser(humanRoleAssignments),
    [humanRoleAssignments],
  );

  const lastOwner = member => isLastOrganizationOwner(member, members);

  async function changeRole(member, membershipRole) {
    if (lastOwner(member) || !canChangeRoles || membershipRole === member.membershipRole) return;

    setChangingUserId(member.userId);
    setError(null);
    setNotice(null);

    try {
      const updated = await workspaceClient.changeOrganizationMemberRole(
        workspace.id,
        member.userId,
        membershipRole,
      );

      if(!alive.current)return;setPendingRole(null);
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

  async function removeMember(member) {
    if (
      !canRemoveOrganizationMember(
        workspace?.membershipRole,
        member.membershipRole,
      )
    ) {
      return;
    }

    if (lastOwner(member)) return;

    setRemovingUserId(member.userId);
    setError(null);
    setNotice(null);

    try {
      await workspaceClient.removeOrganizationMember(
        workspace.id,
        member.userId,
      );

      if(!alive.current)return;
      setMembers(current =>
        current.filter(item => item.userId !== member.userId),
      );

      setHumanRoleAssignments(current =>
        current.filter(item => item.userId !== member.userId),
      );

      setPendingRemoval(null);
      setNotice(`${memberName(member)} was removed from ${workspace.name}.`);
      await onMembershipChanged?.();
    } catch (nextError) {
      setError(nextError);
    } finally {
      setRemovingUserId(null);
    }
  }


  async function changeHumanRole(member, humanRole, enabled) {
    if (!canManageHumanRoles) return;

    const mutationKey = `${member.userId}:${humanRole}`;
    setChangingHumanRole(mutationKey);
    setError(null);
    setNotice(null);

    try {
      if (enabled) {
        await workspaceClient.assignOrganizationHumanRole(
          workspace.id,
          member.userId,
          humanRole,
        );
        if(!alive.current)return;
        setHumanRoleAssignments(current => {
          const alreadyAssigned = current.some(
            item => item.userId === member.userId && item.humanRole === humanRole,
          );
          return alreadyAssigned
            ? current
            : [...current, { userId: member.userId, humanRole }];
        });
        setNotice(`${humanRoleLabel(humanRole)} assigned to ${memberName(member)}.`);
      } else {
        await workspaceClient.deactivateOrganizationHumanRole(
          workspace.id,
          member.userId,
          humanRole,
        );
        if(!alive.current)return;
        setHumanRoleAssignments(current =>
          current.filter(
            item => !(item.userId === member.userId && item.humanRole === humanRole),
          ),
        );
        setNotice(`${humanRoleLabel(humanRole)} removed from ${memberName(member)}.`);
      }
    } catch (nextError) {
      setError(nextError);
    } finally {
      setChangingHumanRole(null);
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
            Access roles control organization permissions. HR responsibilities are separate
            domain roles for Recruiter, Reviewer, and Approver duties.
          </p>
          <p className="organization-management-note">
            {canChangeRoles
              ? "Owners can assign access roles, manage HR responsibilities, and remove members. The last active owner cannot be demoted or removed."
              : "Admins can view members, manage HR responsibilities, and remove ordinary Members. Owner/Admin access changes remain owner-only."}
          </p>
        </div>
        <div className="organization-role-badge">
          <Shield size={15} aria-hidden="true" />
          {organizationRoleLabel(workspace.membershipRole)}
        </div>
      </div>

      <button className="organization-secondary-button" disabled={status === "loading" || changingUserId !== null || removingUserId !== null || changingHumanRole !== null} onClick={()=>setReload(v=>v+1)}>Refresh members</button>
      {pendingRole&&<Modal title="Change member access" onClose={()=>setPendingRole(null)} canDismiss={changingUserId === null}><p>Change {memberName(pendingRole.member)} from {organizationRoleLabel(pendingRole.member.membershipRole)} to {organizationRoleLabel(pendingRole.role)}? Owner and Admin access allows management of the team; HR responsibilities remain separate.</p>{error&&<p role="alert">{error.message}</p>}<button disabled={changingUserId!==null} onClick={()=>changeRole(pendingRole.member,pendingRole.role)}>Confirm access change</button></Modal>}
      {pendingRemoval && <Modal title="Remove organization member" onClose={() => setPendingRemoval(null)} canDismiss={removingUserId === null}><p>Remove {memberName(pendingRemoval)}? This immediately revokes organization access and all active HR responsibilities. If this is your account, you will lose access too.</p><button disabled={removingUserId !== null} onClick={() => removeMember(pendingRemoval)}>Confirm removal</button>{error && <p role="alert">{error.message}</p>}</Modal>}
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
          {sortedMembers.map(member => {
            const assignedRoles = rolesByUser.get(member.userId) ?? new Set();
            return (
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

                <div className="organization-member-access">
                  <span className="organization-control-label">Access role</span>
                  {canChangeRoles && !lastOwner(member) ? (
                    <label className="organization-role-control">
                      <select
                        value={member.membershipRole}
                        disabled={
                          changingUserId !== null ||
                          removingUserId !== null ||
                          changingHumanRole !== null
                        }
                        onChange={event => setPendingRole({member,role:event.target.value})}
                        aria-label={`Access role for ${memberName(member)}`}
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

                  {lastOwner(member) && <p>Transfer ownership before removing or changing this owner.</p>}
                  {!lastOwner(member) && canRemoveOrganizationMember(
                    workspace.membershipRole,
                    member.membershipRole,
                  ) && (
                    <button
                      type="button"
                      className="organization-remove-member-btn"
                      disabled={
                        removingUserId !== null ||
                        changingUserId !== null ||
                        changingHumanRole !== null
                      }
                      onClick={() => setPendingRemoval(member)}
                      aria-label={`Remove ${memberName(member)} from organization`}
                    >
                      {removingUserId === member.userId
                        ? "Removing…"
                        : "Remove member"}
                    </button>
                  )}
                </div>

                <details className="member-hr-details"><summary>Hiring responsibilities</summary><p>These grants are separate from organization access. Recruiters write, Reviewers recommend, and Approvers make final decisions.</p><fieldset className="organization-human-roles">
                  <legend>HR responsibilities</legend>
                  <div className="organization-human-role-options">
                    {HR_HUMAN_ROLE_OPTIONS.map(option => {
                      const checked = assignedRoles.has(option.value);
                      return (
                        <label className="organization-human-role-option" key={option.value}>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={
                              !canManageHumanRoles ||
                              changingHumanRole !== null ||
                              removingUserId !== null ||
                              changingUserId !== null
                            }
                            onChange={event =>
                              changeHumanRole(member, option.value, event.target.checked)
                            }
                            aria-label={`${option.label} for ${memberName(member)}`}
                          />
                          <span>{option.label}</span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset></details>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
