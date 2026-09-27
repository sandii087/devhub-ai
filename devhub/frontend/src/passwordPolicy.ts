export const passwordRequirements = '8–128 characters, including uppercase, lowercase, a number and a special character.'; // pragma: allowlist secret -- public password requirements, not a credential
export function validPassword(value: string) {
  return value.length >= 8 && value.length <= 128 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /[0-9]/.test(value) && /[^\p{L}\p{N}\s]/u.test(value);
}
