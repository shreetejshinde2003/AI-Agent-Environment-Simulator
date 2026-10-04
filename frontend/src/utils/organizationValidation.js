export const ORGANIZATION_NAME_MAX = 120;
export const JOIN_CODE_MAX = 64;

export function organizationNameError(value) {
  const name = value.trim();
  if (!name) return "Enter an organization name.";
  if (name.length > ORGANIZATION_NAME_MAX) {
    return `Organization name must be ${ORGANIZATION_NAME_MAX} characters or fewer.`;
  }
  return null;
}

export function joinCodeError(value) {
  const code = value.trim();
  if (!code) return "Enter an organization join code.";
  if (code.length > JOIN_CODE_MAX) {
    return "Join code is longer than the supported format.";
  }
  return null;
}
