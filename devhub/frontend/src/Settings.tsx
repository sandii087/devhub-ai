import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Camera, CheckCircle2, LockKeyhole, UserRound, ArrowLeft } from 'lucide-react';
import { request, messageOf } from './api';
import { Alert, Avatar, Loading } from './ui';
import { AccountConnections, ChangePassword } from './AuthScreen';
import { passwordRequirements } from './passwordPolicy';
import type { Profile, Session, User } from './types';

export type SettingsTab = 'profile' | 'security' | 'account';
export function settingsTab(): SettingsTab | null {
  const value = window.location.hash.replace('#settings/', '');
  return ['profile', 'security', 'account'].includes(value) ? value as SettingsTab : null;
}

export function Settings({ tab, session, onUser, onLogout, onBack }: {
  tab: SettingsTab; session: Session; onUser: (user: User) => void; onLogout: () => void; onBack: () => void;
}) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState(session.user!.display_name);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false); const [changing, setChanging] = useState(false);
  const [file, setFile] = useState<File | null>(null); const [preview, setPreview] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { const controller = new AbortController(); request<Profile>('/api/v1/me', { signal: controller.signal }).then(setProfile).catch(e => { if (e.name !== 'AbortError') setError(messageOf(e)); }); return () => controller.abort(); }, []);
  useEffect(() => { heading.current?.focus(); setNotice(''); }, [tab]);
  useEffect(() => { if (!file) { setPreview(''); return; } const reader = new FileReader(); reader.onload = () => setPreview(String(reader.result)); reader.readAsDataURL(file); return () => reader.abort(); }, [file]);
  function updated(value: Profile) { setProfile(value); onUser(value); }
  async function saveName(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try { updated(await request<Profile>('/api/v1/me', { method: 'PATCH', csrf: session.csrf_token, body: { display_name: name.trim() } })); setNotice('Profile saved. Looking good!'); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function picture(remove = false) {
    setBusy(true); setError(''); setNotice('');
    try { updated(await request<Profile>('/api/v1/me/avatar', { method: remove ? 'DELETE' : 'PUT', csrf: session.csrf_token, body: remove ? undefined : file })); setFile(null); if (input.current) input.current.value = ''; setNotice(remove ? 'Profile picture removed.' : 'Profile picture updated.'); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function recovery() {
    setBusy(true); setError(''); setNotice('');
    try { const value = await request<{ detail: string }>('/auth/forgot-password', { method: 'POST', body: { email: session.user!.email } }); setNotice(value.detail); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  return <section className="settings-page">
    <button className="text-button settings-back" onClick={onBack}><ArrowLeft size={16} />Back to workspace</button>
    <div className="page-heading"><div><span className="eyebrow">MAKE IT YOURS</span><h1 ref={heading} tabIndex={-1}>Profile &amp; Settings</h1><p>Your identity, your security, your space.</p></div></div>
    <nav className="settings-tabs" aria-label="Settings sections">{(['profile', 'security', 'account'] as const).map((value, i) => { const Icon = [UserRound, LockKeyhole, CheckCircle2][i]; return <a key={value} href={`#settings/${value}`} aria-current={tab === value ? 'page' : undefined}><Icon size={18} />{value[0].toUpperCase() + value.slice(1)}</a>; })}</nav>
    {error && <Alert>{error}</Alert>}{notice && <p className="auth-notice" role="status">{notice}</p>}
    {!profile ? error ? <button className="button secondary" onClick={() => request<Profile>('/api/v1/me').then(value => { setProfile(value); setError(''); }).catch(e => setError(messageOf(e)))}>Try again</button> : <Loading label="Loading your profile…" /> : tab === 'profile' ? <div className="settings-card">
      <h2>Your profile</h2><p className="muted">Help your workspace feel a little more like you.</p>
      <div className="picture-editor"><Avatar name={session.user!.display_name} src={preview || session.user!.avatar_url} /><div><label className="button secondary picture-picker"><Camera size={17} />Choose picture<input ref={input} type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} aria-label="Choose profile picture" onChange={event => { const selected = event.target.files?.[0]; setError(''); if (!selected) return; if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type) || selected.size > 1048576) { setError('Choose a JPEG, PNG or WebP no larger than 1 MiB.'); event.target.value = ''; setFile(null); return; } setFile(selected); }} /></label><p className="muted">JPEG, PNG or WebP · up to 1 MiB / 8 megapixels</p></div></div>
      <div className="settings-actions">{file && <><button className="button primary" disabled={busy} onClick={() => void picture()}>Save picture</button><button className="button secondary" disabled={busy} onClick={() => { setFile(null); if (input.current) input.current.value = ''; }}>Cancel preview</button></>}{session.user!.avatar_url && <button className="text-button" disabled={busy} onClick={() => void picture(true)}>Remove picture</button>}</div>
      <form className="form-stack profile-form" onSubmit={saveName}><label>Display name<input value={name} onChange={e => setName(e.target.value)} required maxLength={100} autoComplete="name" /></label><label>Email<input value={session.user!.email} readOnly type="email" /></label><p className="muted">{profile.email_verified ? 'Email verified' : profile.connected_providers.length ? 'Provider sign-in connected. Local email verification is not recorded.' : 'Email not verified'}</p><button className="button primary" disabled={busy || !name.trim()}>{busy ? 'Saving…' : 'Save profile'}</button></form>
    </div> : tab === 'security' ? <div className="settings-card"><h2>Sign-in &amp; security</h2><p className="muted">Keep access to your workspace in your hands.</p><div className="security-item"><h3>Password</h3><p>{passwordRequirements}</p>{profile.password_enabled && session.email_enabled ? <button className="button secondary" onClick={() => setChanging(true)}>Change password</button> : <p className="muted">This account uses its sign-in provider. Manage your password with Google or GitHub.</p>}</div><div className="security-item"><h3>Account recovery</h3><p className="muted">Request a secure link for an eligible verified email/password account.</p><button className="button secondary" disabled={busy || !session.email_enabled || !session.email_delivery} onClick={() => void recovery()}>Send password reset email</button>{!session.email_delivery && <p className="muted">Email recovery is not configured by your operator yet.</p>}</div><div className="security-item"><h3>Your sessions</h3><p className="muted">Changing or resetting your password signs you out on all devices. Sign out when using a shared device.</p></div></div> : <div className="settings-card"><h2>Your DevHub account</h2><p className="muted">One account for your projects and connected providers.</p><dl className="account-details"><dt>Email</dt><dd>{session.user!.email}</dd><dt>Account ID</dt><dd>{session.user!.id}</dd><dt>Connected providers</dt><dd>{profile.connected_providers.join(', ') || 'No OAuth providers connected'}</dd></dl><h3>Connect a sign-in provider</h3><p className="muted">For your protection, sign in again before connecting a new provider.</p><AccountConnections session={session} onPasswordChanged={onLogout} showPassword={false} /></div>}
    {changing && <ChangePassword session={session} onClose={() => setChanging(false)} onChanged={onLogout} />}
  </section>;
}
