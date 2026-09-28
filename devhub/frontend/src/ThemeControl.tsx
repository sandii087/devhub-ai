import { useEffect, useState } from 'react';
import { SunMoon } from 'lucide-react';

type Theme = 'system' | 'light' | 'dark';
export function ThemeControl() {
  const [theme, setTheme] = useState<Theme>(() => {
    try { const saved = window.localStorage.getItem('devhub-theme'); return saved === 'light' || saved === 'dark' ? saved : 'system'; }
    catch { return 'system'; }
  });
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => { document.documentElement.dataset.theme = theme === 'system' ? media.matches ? 'dark' : 'light' : theme; };
    apply(); media.addEventListener('change', apply);
    try { window.localStorage.setItem('devhub-theme', theme); } catch { /* Theme still works with storage blocked. */ }
    return () => media.removeEventListener('change', apply);
  }, [theme]);
  return <label className="theme-control"><SunMoon size={17} aria-hidden="true" /><span className="sr-only">Appearance</span><select value={theme} onChange={event => setTheme(event.target.value as Theme)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>;
}
