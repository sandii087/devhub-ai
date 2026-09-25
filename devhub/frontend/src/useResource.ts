import { useEffect, useState } from 'react';
import { ApiError, messageOf, request } from './api';

export function useResource<T>(path: string | null) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ path: string | null; data?: T; error?: string; loading: boolean }>({ path, loading: !!path });
  useEffect(() => {
    if (!path) { setResult({ path, loading: false }); return; }
    const controller = new AbortController();
    setResult(previous => ({ path, data: previous.path === path ? previous.data : undefined, loading: true }));
    request<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setResult({ path, data, loading: false });
    }).catch(error => {
      if (!controller.signal.aborted) setResult(previous => ({ path, data: error instanceof ApiError && [401,403,404].includes(error.status) ? undefined : previous.path === path ? previous.data : undefined, loading: false, error: messageOf(error) }));
    });
    return () => controller.abort();
  }, [path, revision]);
  const current = result.path === path ? result : { path, loading: !!path, data: undefined, error: undefined };
  return { ...current, reload: () => setRevision(value => value + 1) };
}
