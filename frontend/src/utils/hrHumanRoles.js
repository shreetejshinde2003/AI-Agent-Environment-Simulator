export const HR_HUMAN_ROLE_OPTIONS = [
  {
    value: "hr_recruiter",
    label: "HR Recruiter",
    description: "Create and manage hiring requirements and JD drafts.",
  },
  {
    value: "hr_reviewer",
    label: "HR Reviewer",
    description: "Review job descriptions and request revisions.",
  },
  {
    value: "hr_approver",
    label: "HR Approver",
    description: "Approve or reject reviewed job descriptions.",
  },
];

export const humanRoleLabel = role =>
  HR_HUMAN_ROLE_OPTIONS.find(option => option.value === role)?.label ?? "Unknown HR role";

export const canManageHrHumanRoles = membershipRole =>
  membershipRole === "owner" || membershipRole === "admin";

export function humanRolesByUser(assignments = []) {
  const result = new Map();
  for (const assignment of assignments) {
    const roles = result.get(assignment.userId) ?? new Set();
    roles.add(assignment.humanRole);
    result.set(assignment.userId, roles);
  }
  return result;
}
