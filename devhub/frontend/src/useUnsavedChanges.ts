import { useEffect } from 'react';

// Navigation stays synchronous, so a cancelled action never mutates the route.
export function allowNavigation() {
  return window.dispatchEvent(new Event('devhub-before-navigate', { cancelable: true }));
}

export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const leave = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    const navigate = (event: Event) => {
      if (!window.confirm('Discard your unsaved changes?')) event.preventDefault();
    };
    window.addEventListener('beforeunload', leave);
    window.addEventListener('devhub-before-navigate', navigate);
    return () => {
      window.removeEventListener('beforeunload', leave);
      window.removeEventListener('devhub-before-navigate', navigate);
    };
  }, [dirty]);
}
