export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; }
}

export async function request<T>(path: string, options: { method?: string; body?: unknown; csrf?: string | null; signal?: AbortSignal } = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.csrf && !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) headers['X-CSRF-Token'] = options.csrf;
  let response: Response;
  try {
    response = await fetch(path, { method, credentials: 'same-origin', headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: options.signal });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'We could not reach DevHub. Check your connection and try again.');
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('session-expired'));
    let message = response.status === 409 ? 'This item changed since you opened it. Refresh and try again.' : 'Something went wrong. Please try again.';
    if (typeof data?.detail === 'string') message = data.detail;
    else if (typeof data?.detail?.message === 'string') message = data.detail.message;
    else if (typeof data?.detail?.detail === 'string') message = data.detail.detail;
    else if (Array.isArray(data?.detail)) message = data.detail.map((issue: { msg?: string }) => issue.msg ?? 'Invalid input').join('. ');
    throw new ApiError(response.status, message);
  }
  if (data === null) throw new ApiError(response.status, 'DevHub returned an unexpected response. Please try again.');
  return data as T;
}

export const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
