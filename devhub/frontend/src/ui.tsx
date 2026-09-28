import { useEffect, useId, useRef, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { AlertCircle, Eye, EyeOff, LoaderCircle, X } from 'lucide-react';

export function Alert({ children, id }: { children: ReactNode; id?: string }) {
  return <div id={id} className="alert" role="alert"><AlertCircle size={18} /><span>{children}</span></div>;
}

export function Loading({ label = 'Loading your workspace…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" size={22} /><span>{label}</span></div>;
}

export function Empty({ icon, title, children, action }: { icon: ReactNode; title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{children}</p>{action}</div>;
}

export function Avatar({ name, small = false, src }: { name: string; small?: boolean; src?: string | null }) {
  return <span className={`avatar ${small ? 'small' : ''}`} aria-label={name}>{src ? <img src={src} alt="" /> : name.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') || '?'}</span>;
}

export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const trigger = document.activeElement as HTMLElement;
    dialog?.showModal();
    return () => { dialog?.close(); if (trigger.isConnected) trigger.focus(); };
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

export function PasswordField({ label, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return <div className="password-field"><label htmlFor={id}>{label}</label><div className="password-control"><input autoCapitalize="none" autoCorrect="off" spellCheck={false} {...props} id={id} type={visible ? 'text' : 'password'} aria-describedby={[props['aria-describedby'], hint ? `${id}-hint` : ''].filter(Boolean).join(' ') || undefined} /><button type="button" className="icon-button" aria-label={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`} aria-pressed={visible} disabled={props.disabled} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>{hint && <small id={`${id}-hint`} className="field-hint">{hint}</small>}</div>;
}

export function Skeleton({ label = 'Loading…' }: { label?: string }) {
  return <div className="page-skeleton" role="status"><span className="sr-only">{label}</span><div aria-hidden="true"><i /><i /><i /></div></div>;
}
