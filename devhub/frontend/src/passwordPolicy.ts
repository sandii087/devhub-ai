export const passwordRequirements = '8–128 characters, including uppercase, lowercase, a number and a special character.'; // pragma: allowlist secret -- public password requirements, not a credential
// HTML maxlength counts UTF-16 units; 128 Unicode code points can need 256 units.
export const passwordInputMaxLength = 256;
export function validPassword(value: string) {
  // Match Python len(str), without normalizing or changing the password.
  const length = Array.from(value).length;
  return length >= 8 && length <= 128 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /[0-9]/.test(value) && /[^\p{L}\p{N}\s]/u.test(value);
}
