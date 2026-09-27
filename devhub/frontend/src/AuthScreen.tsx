import { useState, type FormEvent } from 'react';
import { ArrowRight, Code2, Github, LoaderCircle, ShieldCheck } from 'lucide-react';
import { messageOf, request } from './api';
import { Alert } from './ui';
import type { Session } from './types';

export function AuthScreen({ session, onLogin, authLink = '' }: {
  session: Session; onLogin: (value: Session) => void; authLink?: string;
}) {
  const params = new URLSearchParams(authLink.replace(/^#/, ''));
  const [token] = useState(params.get('reset-password') ?? params.get('verify-email') ?? '');
  const [mode, setMode] = useState(params.has('reset-password') ? 'reset' : params.has('verify-email') ? 'verify' : 'login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(params.has('auth-error') ? (params.get('auth-error') === 'link'
    ? 'An account already exists. Sign in with your existing method, then connect this provider from your account.'
    : 'Sign-in was cancelled, expired, or could not be completed. Please try again.') : '');
  const [notice, setNotice] = useState('');
  const providers = session.providers ?? (session.auth_mode === 'github' ? ['github'] : []);
  const change = (next: string) => { setMode(next); setError(''); setNotice(''); };
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice('');
    const values = new FormData(event.currentTarget);
    const email = String(values.get('email') ?? '');
    const password = String(values.get('password') ?? '');
    if (['signup', 'reset', 'verify'].includes(mode) && password !== values.get('confirm')) {
      setError('Passwords do not match.'); return;
    }
    setBusy(true);
    try {
      if (mode === 'login') {
        onLogin(await request<Session>('/auth/email-login', { method: 'POST', body: { email, password } }));
      } else {
        const path = { signup: 'signup', forgot: 'forgot-password', reset: 'reset-password', verify: 'verify-email', resend: 'resend-verification' }[mode];
        const body = mode === 'signup' ? { email, password, display_name: values.get('name') }
          : ['reset', 'verify'].includes(mode) ? { token, password } : { email };
        const result = await request<{ detail: string }>(`/auth/${path}`, { method: 'POST', body });
        setNotice(result.detail);
        if (['reset', 'verify'].includes(mode)) { setMode('login'); onLogin({ ...session, user: null, csrf_token: null }); }
      }
    } catch (cause) { setError(messageOf(cause)); }
    finally { setBusy(false); }
  }
  const title = { login: 'Welcome to DevHub', signup: 'Create your account', forgot: 'Forgot your password?', reset: 'Choose a new password', verify: 'Verify your email', resend: 'Resend verification' }[mode];
  return <main className="login-page"><section className="login-story">
    <a className="brand" href="/"><span className="brand-icon"><Code2 /></span>devhub<span className="brand-dot">.</span></a>
    <div className="login-pitch"><span className="pill-light">YOUR TEAM’S NEXT CHAPTER</span><h1>Good ideas deserve<br />a great workspace.</h1><p>Plan the work. Share the thinking.<br />Build something that matters, together.</p></div>
    <div className="login-footer">A shared space for the people behind the code.</div>
    <div className="orbit orbit-one" /><div className="orbit orbit-two" />
  </section><section className="login-form-wrap"><div className="login-form">
    <span className="eyebrow">YOUR WORK STARTS HERE</span><h2>{title}</h2>
    <p className="muted">{mode === 'verify' ? 'Choose your password to confirm ownership of this email address.' : 'Your people, projects, and next big idea.'}</p>
    {error && <Alert>{error}</Alert>}{notice && <p className="auth-notice" role="status">{notice}</p>}
    {['login', 'signup'].includes(mode) && <><div className="auth-providers">
      {providers.includes('google') ? <a className="button secondary large" href="/auth/google/login">Continue with Google</a> : <button className="button secondary large" disabled title="Google sign-in is not configured">Continue with Google</button>}
      {providers.includes('github') ? <a className="button secondary large" href="/auth/login"><Github size={18} />Continue with GitHub</a> : <button className="button secondary large" disabled title="GitHub sign-in is not configured"><Github size={18} />Continue with GitHub</button>}
    </div><div className="auth-divider">or use your email</div></>}
    {session.email_enabled ? <form className="form-stack" onSubmit={submit} key={mode}>
      {mode === 'signup' && <label>Name<input name="name" autoComplete="name" maxLength={100} required /></label>}
      {!['reset', 'verify'].includes(mode) && <label>Email<input name="email" type="email" autoComplete="email" maxLength={254} required /></label>}
      {!['forgot', 'resend'].includes(mode) && <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={['signup', 'reset', 'verify'].includes(mode) ? 15 : 1} maxLength={128} required /></label>}
      {['signup', 'reset', 'verify'].includes(mode) && <><small className="muted">Use a unique passphrase of 15–128 characters.</small><label>Confirm password<input name="confirm" type="password" autoComplete="new-password" minLength={15} maxLength={128} required /></label></>}
      <button className="button primary large" disabled={busy || (['signup', 'forgot', 'resend'].includes(mode) && !session.email_delivery)}>{busy ? <LoaderCircle className="spin" size={18} /> : <>{({ login: 'Login', signup: 'Create account', forgot: 'Send reset link', reset: 'Reset password', verify: 'Verify email', resend: 'Send verification link' })[mode]}<ArrowRight size={18} /></>}</button>
      {!session.email_delivery && mode !== 'login' && <p className="muted">Email delivery is not configured yet.</p>}
    </form> : <Alert>Email sign-in is not configured yet. Use an available provider above.</Alert>}
    <div className="auth-navigation">
      {session.user && <button onClick={() => onLogin(session)}>Return to workspace</button>}
      {mode === 'login' ? <><button onClick={() => change('forgot')}>Forgot password?</button><button onClick={() => change('signup')}>Create account</button><button onClick={() => change('resend')}>Resend verification email</button></> : <button onClick={() => change('login')}>Back to login</button>}
    </div><p className="login-security"><ShieldCheck size={15} />Your workspace. Your team. Secure by design.</p>
  </div></section></main>;
}

export function AccountConnections({ session }: { session: Session }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function connect(provider: string) {
    setBusy(true); setError('');
    try {
      const result = await request<{ url: string }>(`/auth/link/${provider}`, { method: 'POST', csrf: session.csrf_token });
      window.location.assign(result.url);
    } catch (cause) { setError(messageOf(cause)); setBusy(false); }
  }
  return <div className="account-connections">{session.providers?.map(provider => <button key={provider} disabled={busy} onClick={() => void connect(provider)}>Connect {provider === 'google' ? 'Google' : 'GitHub'}</button>)}{error && <Alert>{error}</Alert>}</div>;
}
