export function workspaceOptions(workspaceData) {
  if (!workspaceData?.personalWorkspace) return [];
  return [
    workspaceData.personalWorkspace,
    ...(workspaceData.organizations ?? []),
  ];
}

export function resolveActiveWorkspaceId(workspaceData, preferredId) {
  const options = workspaceOptions(workspaceData);
  if (!options.length) return null;
  if (preferredId && options.some(workspace => workspace.id === preferredId)) {
    return preferredId;
  }
  return workspaceData.personalWorkspace.id;
}
