export function canManageRecycleBin(workspace) {
  return workspace?.kind === "personal" || ["owner", "admin"].includes(workspace?.membershipRole);
}
export function canPurgeRecycleBin(workspace) {
  return workspace?.kind === "personal" || workspace?.membershipRole === "owner";
}
