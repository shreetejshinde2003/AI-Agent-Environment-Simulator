export function canManageRecycleBin(workspace) {
  return workspace?.kind === "personal" || ["owner", "admin"].includes(workspace?.membershipRole);
}
export function canPurgeRecycleBin(workspace) {
  return workspace?.kind === "personal" || workspace?.membershipRole === "owner";
}

// Unknown eligibility fails closed until an authoritative refresh.
export function canDeleteItem(item) { return item?.permanentDeletionEligible === true; }
