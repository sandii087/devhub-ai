import { useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { CircleHelp, Mail } from 'lucide-react';
import { Modal } from './ui';

const supportEmail = 'keeponn87@gmail.com';

export function SupportContact() {
  const [open, setOpen] = useState(false);
  function containFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return;
    const controls = event.currentTarget.querySelectorAll<HTMLElement>('button, a[href]');
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first?.focus();
    }
  }
  return <>
    <button type="button" className="nav-item" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>
      <CircleHelp size={19} aria-hidden="true" /><span>Help &amp; Support</span>
    </button>
    {open && createPortal(
      <div onKeyDown={containFocus}><Modal title="Need help?" onClose={() => setOpen(false)}>
        <div className="form-stack">
          <p className="muted">Contact the DevHub owner directly if you have a problem, need assistance, have a question, or want to share feedback.</p>
          <a className="button primary" href={`mailto:${supportEmail}`}><Mail size={18} aria-hidden="true" />Email Support</a>
          <p className="field-hint">Opens your email app. You can also email {supportEmail} from your preferred email service.</p>
        </div>
      </Modal></div>, document.body,
    )}
  </>;
}
