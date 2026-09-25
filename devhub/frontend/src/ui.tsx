import { useEffect, useRef, type ReactNode } from 'react';
import { AlertCircle, LoaderCircle, X } from 'lucide-react';

export function Alert({ children }: { children: ReactNode }) {
  return <div className="alert" role="alert"><AlertCircle size={18} /><span>{children}</span></div>;
}

export function Loading({ label = 'Loading your workspace…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" size={22} /><span>{label}</span></div>;
}

export function Empty({ icon, title, children, action }: { icon: ReactNode; title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{children}</p>{action}</div>;
}

export function Avatar({ name, small = false }: { name: string; small?: boolean }) {
  return <span className={`avatar ${small ? 'small' : ''}`} aria-label={name}>{name.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') || '?'}</span>;
}

export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return <dialog ref={ref} className={`modal ${wide ? 'wide' : ''}`} onCancel={event => { event.preventDefault(); onClose(); }} aria-label={title}>
    <div className="modal-heading"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={20} /></button></div>
    {children}
  </dialog>;
}

export function dateLabel(value?: string | null) {
  if (!value) return 'Not yet';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
