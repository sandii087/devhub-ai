import { useState, type FormEvent } from 'react';
import { LoaderCircle, Plus, Shield, Trash2, Users } from 'lucide-react';
import { messageOf, request } from './api';
import { useResource } from './useResource';
import { Alert, Avatar, Empty, Loading, Modal } from './ui';
import { Pagination } from './ProjectView';
import type { Member, Organization, Page, Session } from './types';

export function MembersPanel({ org, session, onChange }: { org: Organization; session: Session; onChange: () => void }) {
  const [page, setPage] = useState(0);
  const path = `/api/v1/organizations/${org.id}/members`;
  const members = useResource<Page<Member>>(`${path}?limit=100&offset=${page * 100}`);
  const [showAdd, setShowAdd] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [removing, setRemoving] = useState<Member | null>(null);
  const allowedRoles = org.role === 'owner' ? ['member', 'viewer', 'admin', 'owner'] : ['member', 'viewer'];
  const reload = () => { members.reload(); onChange(); };
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    try { await request(path, { method: 'POST', csrf: session.csrf_token, body: { email: String(data.get('email')).trim(), role: data.get('role') } }); setShowAdd(false); reload(); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function update(member: Member, role: string) {
    setBusy(true); setError('');
    try { await request(`${path}/${member.user_id}`, { method: 'PATCH', csrf: session.csrf_token, body: { role } }); reload(); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setError('');
    try { await request(`${path}/${removing!.user_id}`, { method: 'DELETE', csrf: session.csrf_token }); setRemoving(null); reload(); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  return <><div className="page-heading"><div><div className="eyebrow">BETTER TOGETHER</div><h1>Your people.</h1><p>Give everyone the right place in {org.name}.</p></div><button className="button primary" onClick={() => { setShowAdd(true); setError(''); }}><Plus size={17} />Add member</button></div>{(error && !showAdd && !removing || members.error) && <Alert>{error || members.error}</Alert>}
    <div className="panel"><div className="panel-heading"><div><h3>Organization members <span className="count">{members.data?.total ?? '—'}</span><p>Roles apply across your organization.</p></h3></div><Shield size={21} className="muted" /></div>{members.loading && !members.data ? <Loading label="Loading members…" /> : !members.data?.items.length ? <Empty icon={<Users size={25} />} title="No members on this page">Add a teammate to collaborate.</Empty> : <div className="table-scroll"><table><thead><tr><th>Member</th><th>Role</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{members.data.items.map(member => { const canManage = org.role === 'owner' || !['owner', 'admin'].includes(member.role); return <tr key={member.user_id}><td><div className="person"><Avatar name={member.display_name || member.email} /><div><strong>{member.display_name || member.email}{member.user_id === session.user!.id && <span className="you-label">You</span>}</strong><span>{member.email}</span></div></div></td><td>{canManage && member.active !== false ? <select aria-label={`Role for ${member.email}`} className="role-select" disabled={busy} value={member.role} onChange={event => update(member, event.target.value)}>{Array.from(new Set([...allowedRoles, member.role])).map(role => <option key={role} value={role}>{role[0].toUpperCase() + role.slice(1)}</option>)}</select> : <span className="badge neutral">{member.role}</span>}</td><td><span className={`badge ${member.active === false ? 'neutral' : 'green'}`}>{member.active === false ? 'Inactive' : 'Active'}</span></td><td>{canManage && member.active !== false && <button className="icon-button" aria-label={`Remove ${member.email}`} onClick={() => { setRemoving(member); setError(''); }}><Trash2 size={16} /></button>}</td></tr>; })}</tbody></table></div>}<Pagination page={page} total={members.data?.total ?? 0} onChange={setPage} /></div>
    {showAdd && <Modal title="Add a teammate" onClose={() => setShowAdd(false)}><form className="form-stack" onSubmit={add}>{error && <Alert>{error}</Alert>}<p className="muted">Your teammate needs to sign in to DevHub once before you can add their existing account.</p><label>Email address<input autoFocus name="email" type="email" maxLength={320} required placeholder="teammate@company.com" /></label><label>Organization role<select name="role" defaultValue="member">{allowedRoles.map(role => <option key={role} value={role}>{role[0].toUpperCase() + role.slice(1)}</option>)}</select></label><p className="field-hint">Members contribute to organization projects. Viewers have read-only access. Administrators manage members and integrations.</p><div className="modal-actions"><button type="button" className="button secondary" onClick={() => setShowAdd(false)}>Cancel</button><button className="button primary" disabled={busy}>{busy && <LoaderCircle size={16} className="spin" />}Add member</button></div></form></Modal>}
    {removing && <Modal title="Remove organization access?" onClose={() => setRemoving(null)}><div className="form-stack">{error && <Alert>{error}</Alert>}<p>{removing.display_name || removing.email} will lose access to this organization and its projects. Their previous contributions remain.</p><div className="modal-actions"><button className="button secondary" onClick={() => setRemoving(null)}>Cancel</button><button className="button danger" disabled={busy} onClick={remove}>Remove member</button></div></div></Modal>}
  </>;
}
