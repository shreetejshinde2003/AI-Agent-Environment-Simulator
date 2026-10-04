export const ORGANIZATION_ROLE_LABELS = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};

export const organizationRoleLabel = role =>
  ORGANIZATION_ROLE_LABELS[role] ?? "Unknown";

export const canViewOrganizationMembers = role =>
  role === "owner" || role === "admin";

export const canChangeOrganizationRoles = role => role === "owner";
