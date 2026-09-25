import { useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Check, Circle, GitBranch, LayoutGrid, ListTodo, LoaderCircle, LockKeyhole, MessageSquare, Plus, Sparkles, Search, Send, Users } from 'lucide-react';
import { messageOf, request } from './api';
import { useResource } from './useResource';
import { Alert, Avatar, dateLabel, Empty, Loading, Modal } from './ui';
import { statuses, TaskForm } from './TaskForm';
import { GitHubPanel } from './GitHubPanel';
import { AIPanel } from './AIPanel';
import type { Comment, Discussion, Member, Organization, Page, Project, Session, Task, TaskStatus } from './types';

export function Pagination({ page, total, onChange }: { page: number; total: number; onChange: (page: number) => void }) {
  if (total <= 100) return null;
  return <div className="pagination"><span>Showing {page * 100 + 1}–{Math.min((page + 1) * 100, total)} of {total}</span><button className="button secondary" disabled={page === 0} onClick={() => onChange(page - 1)}><ArrowLeft size={15} />Previous</button><button className="button secondary" disabled={(page + 1) * 100 >= total} onClick={() => onChange(page + 1)}>Next<ArrowRight size={15} /></button></div>;
}

export function ProjectView({ project, org, session, members, onBack }: { project: Project; org: Organization; session: Session; members: Member[]; onBack: () => void }) {
  const [tab, setTab] = useState<'tasks' | 'discussions' | 'repositories' | 'ai'>('tasks');
  const [showAccess, setShowAccess] = useState(false);
  const role = project.effective_role ?? project.role ?? org.role;
  const canEdit = role !== 'viewer' && !!role;
  const canManage = ['maintainer', 'owner', 'admin'].includes(role ?? '');
  const admin = ['owner', 'admin'].includes(org.role ?? '');
  const path = `/api/v1/organizations/${org.id}/projects/${project.id}`;
  return <>
    <button className="back-link" onClick={onBack}><ArrowLeft size={15} />All projects</button>
    <div className="page-heading"><div><div className="eyebrow"><span className="project-mark">{project.name.slice(0, 1).toUpperCase()}</span>PROJECT WORKSPACE</div><h1>{project.name}</h1><p>{project.description || 'A shared space to plan, build, and keep the conversation moving.'}</p></div><div className="heading-actions"><span className="badge neutral">{project.visibility === 'private' ? <LockKeyhole size={13} /> : <Users size={13} />}{project.visibility === 'private' ? 'Private project' : 'Organization project'}</span>{canManage && <button className="button secondary" onClick={() => setShowAccess(true)}><Users size={16} />Manage access</button>}</div></div>
    <div className="tabs" aria-label="Project sections">{([{ id: 'tasks', label: 'Task board', icon: LayoutGrid }, { id: 'discussions', label: 'Discussions', icon: MessageSquare }, { id: 'ai', label: 'AI assistant', icon: Sparkles }, ...(admin ? [{ id: 'repositories', label: 'Repositories', icon: GitBranch }] : [])] as const).map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id as typeof tab)} aria-current={tab === item.id ? 'page' : undefined}><item.icon size={17} />{item.label}</button>)}</div>
    {tab === 'tasks' && <TaskBoard key={project.id} path={path} session={session} members={members} canEdit={canEdit} canManage={canManage} />}
    {tab === 'discussions' && <Discussions key={project.id} path={path} session={session} members={members} canEdit={canEdit} />}
    {tab === 'ai' && <AIPanel path={path} session={session} admin={admin} canEdit={canEdit} />}
    {tab === 'repositories' && admin && <GitHubPanel org={org} project={project} session={session} />}
    {showAccess && <ProjectAccess path={path} session={session} onClose={() => setShowAccess(false)} />}
  </>;
}

function TaskBoard({ path, session, members, canEdit, canManage }: { path: string; session: Session; members: Member[]; canEdit: boolean; canManage: boolean }) {
  const [page, setPage] = useState(0);
  const tasks = useResource<Page<Task>>(`${path}/tasks?limit=100&offset=${page * 100}`);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Task | 'new' | null>(null);
  const [initialStatus, setInitialStatus] = useState<TaskStatus>('todo');
  const filtered = (tasks.data?.items ?? []).filter(task => task.title.toLowerCase().includes(search.toLowerCase()));
  const create = (status: TaskStatus = 'todo') => { setInitialStatus(status); setSelected('new'); };
  const memberName = (id: string) => members.find(member => member.user_id === id)?.display_name || (session.user?.id === id ? session.user.display_name : 'Team member');
  return <>
    <div className="section-toolbar"><div><h2>Keep the work moving <span className="count">{tasks.data?.total ?? '—'}</span></h2><p>From the first idea to the final detail.</p></div><div className="toolbar-actions"><div className="search-field"><Search size={17} /><input aria-label="Search tasks on this page" placeholder="Search tasks…" value={search} onChange={event => setSearch(event.target.value)} /></div>{canEdit && <button className="button primary" onClick={() => create()}><Plus size={17} />New task</button>}</div></div>
    {tasks.error && <Alert>{tasks.error} <button className="text-button" onClick={tasks.reload}>Try again</button></Alert>}
    {tasks.loading && !tasks.data ? <Loading label="Loading tasks…" /> : <div className="board">{statuses.map(status => {
      const items = filtered.filter(task => task.status === status.value);
      return <section key={status.value} className={`board-column ${status.className}`} aria-label={status.label}><div className="column-heading"><div><span className={`status-dot ${status.className}`} /><h3>{status.label}</h3><span>{items.length}</span></div>{canEdit && <button className="icon-button" aria-label={`Add ${status.label.toLowerCase()} task`} onClick={() => create(status.value)}><Plus size={17} /></button>}</div><div className="column-content">{items.map(task => <button key={task.id} className="task-card" onClick={() => setSelected(task)}><div className="task-card-top"><span className={`priority ${task.priority}`}><span />{task.priority}</span>{task.status === 'done' && <Check size={16} className="success-text" />}</div><h4>{task.title}</h4>{task.description && <p>{task.description}</p>}<div className="task-card-footer"><span className="task-key"><ListTodo size={13} />{task.id.slice(0, 8)}</span>{task.assignee_id ? <Avatar name={memberName(task.assignee_id)} small /> : <span className="unassigned" title="Unassigned"><Users size={14} /></span>}</div></button>)}{!items.length && <div className="column-empty"><Circle size={22} /><span>{search ? 'No matching tasks' : status.value === 'done' ? 'Good things take a little work.' : 'A little room for what’s next.'}</span></div>}{canEdit && <button className="add-card" onClick={() => create(status.value)}><Plus size={16} />Add task</button>}</div></section>;
    })}</div>}
    <Pagination page={page} total={tasks.data?.total ?? 0} onChange={setPage} />
    {selected && <TaskForm task={selected === 'new' ? undefined : selected} initialStatus={initialStatus} path={`${path}/tasks`} csrf={session.csrf_token} user={session.user!} members={members} canEdit={canEdit} canDelete={selected !== 'new' && (canManage || (selected.created_by ?? selected.creator_id) === session.user!.id)} onClose={() => setSelected(null)} onSaved={tasks.reload} />}
  </>;
}

function Discussions({ path, session, members, canEdit }: { path: string; session: Session; members: Member[]; canEdit: boolean }) {
  const [page, setPage] = useState(0);
  const discussions = useResource<Page<Discussion>>(`${path}/discussions?limit=100&offset=${page * 100}`);
  const [selected, setSelected] = useState<Discussion | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    try { const discussion = await request<Discussion>(`${path}/discussions`, { method: 'POST', csrf: session.csrf_token, body: { title: String(data.get('title')).trim(), body: String(data.get('body')).trim() } }); setCreating(false); discussions.reload(); setSelected(discussion); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  return <><div className="section-toolbar"><div><h2>A place to think together <span className="count">{discussions.data?.total ?? '—'}</span></h2><p>Share ideas, ask questions, and give decisions a home.</p></div>{canEdit && <button className="button primary" onClick={() => { setCreating(true); setError(''); }}><Plus size={17} />New discussion</button>}</div>
    {discussions.error && <Alert>{discussions.error}<button className="text-button" onClick={discussions.reload}>Try again</button></Alert>}
    {discussions.loading && !discussions.data ? <Loading label="Loading discussions…" /> : !discussions.data?.items.length ? <Empty icon={<MessageSquare size={28} />} title="Start the conversation" action={canEdit && <button className="button primary" onClick={() => setCreating(true)}>Create a discussion</button>}>Your team's ideas and decisions belong here.</Empty> : <div className="discussion-list">{discussions.data.items.map(discussion => <button className="discussion-row" key={discussion.id} onClick={() => setSelected(discussion)}><div className="discussion-icon"><MessageSquare size={20} /></div><div><h3>{discussion.title}</h3><p>{discussion.body}</p><span>{dateLabel(discussion.created_at)}</span></div><ArrowRight size={18} /></button>)}</div>}
    <Pagination page={page} total={discussions.data?.total ?? 0} onChange={setPage} />
    {creating && <Modal title="Start a discussion" onClose={() => setCreating(false)}><form className="form-stack" onSubmit={create}>{error && <Alert>{error}</Alert>}<label>Title<input autoFocus name="title" maxLength={200} required placeholder="What’s on your mind?" /></label><label>Your message<textarea name="body" maxLength={20000} required rows={7} placeholder="Share the context with your team…" /></label><div className="modal-actions"><button type="button" className="button secondary" onClick={() => setCreating(false)}>Cancel</button><button className="button primary" disabled={busy}>{busy && <LoaderCircle size={16} className="spin" />}Post discussion</button></div></form></Modal>}
    {selected && <DiscussionThread discussion={selected} path={`${path}/discussions/${selected.id}`} session={session} members={members} canEdit={canEdit} onClose={() => setSelected(null)} />}
  </>;
}

function DiscussionThread({ discussion, path, session, members, canEdit, onClose }: { discussion: Discussion; path: string; session: Session; members: Member[]; canEdit: boolean; onClose: () => void }) {
  const [page, setPage] = useState(0);
  const comments = useResource<Page<Comment>>(`${path}/comments?limit=100&offset=${page * 100}`);
  const [body, setBody] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const nameFor = (id?: string) => id === session.user!.id ? session.user!.display_name : members.find(member => member.user_id === id)?.display_name ?? 'Team member';
  async function comment(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await request(`${path}/comments`, { method: 'POST', csrf: session.csrf_token, body: { body: body.trim() } }); setBody(''); comments.reload(); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  return <Modal title="Discussion" onClose={onClose} wide><article className="thread"><h2>{discussion.title}</h2><div className="author-line"><Avatar name={nameFor(discussion.created_by ?? discussion.creator_id)} small /><strong>{nameFor(discussion.created_by ?? discussion.creator_id)}</strong><span>{dateLabel(discussion.created_at)}</span></div><p className="prose">{discussion.body}</p><div className="thread-divider"><h3>Replies <span className="count">{comments.data?.total ?? 0}</span></h3></div>{comments.error && <Alert>{comments.error}<button className="text-button" onClick={comments.reload}>Try again</button></Alert>}{comments.loading && !comments.data && <Loading label="Loading replies…" />}{comments.data?.items.map(item => { const name = item.author?.display_name ?? nameFor(item.author_id ?? item.created_by); return <div className="comment" key={item.id}><Avatar name={name} small /><div><div className="comment-heading"><strong>{name}</strong><span>{dateLabel(item.created_at)}</span></div><p className="prose">{item.body}</p></div></div>; })}{comments.data?.total === 0 && <p className="muted">No replies yet. Bring your perspective to the conversation.</p>}<Pagination page={page} total={comments.data?.total ?? 0} onChange={setPage} />{canEdit && <form className="form-stack comment-form" onSubmit={comment}>{error && <Alert>{error}</Alert>}<label>Add a reply<textarea value={body} onChange={event => setBody(event.target.value)} maxLength={10000} rows={3} required placeholder="Write a thoughtful reply…" /></label><button className="button primary" disabled={busy || !body.trim()}>{busy ? <LoaderCircle size={16} className="spin" /> : <Send size={16} />}Post reply</button></form>}</article></Modal>;
}

function ProjectAccess({ path, session, onClose }: { path: string; session: Session; onClose: () => void }) {
  const members = useResource<Page<Member>>(`${path}/members?limit=100`);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form); setBusy(true); setError('');
    try { await request(`${path}/members`, { method: 'POST', csrf: session.csrf_token, body: { email: values.get('email'), role: values.get('role') } }); form.reset(); members.reload(); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function remove(id: string) {
    setBusy(true); setError('');
    try { await request(`${path}/members/${id}`, { method: 'DELETE', csrf: session.csrf_token }); members.reload(); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  return <Modal title="Project access" onClose={onClose}><div className="form-stack"><p className="muted">Add someone who already belongs to this organization. Organization administrators retain access.</p>{(error || members.error) && <Alert>{error || members.error}</Alert>}<form className="form-stack" onSubmit={add}><label>Member email<input name="email" required type="email" placeholder="teammate@company.com" /></label><label>Project role<select name="role" defaultValue="contributor"><option value="contributor">Contributor — create and update work</option><option value="viewer">Viewer — read only</option><option value="maintainer">Maintainer — manage project access</option></select></label><button className="button primary" disabled={busy}>Add project member</button></form>{members.loading && !members.data && <Loading />}{members.data?.items.map(member => <div className="access-row" key={member.user_id}><Avatar name={member.display_name || member.email} small /><div><strong>{member.display_name || member.email}</strong><span>{member.role}</span></div><button className="text-button danger-text" disabled={busy} onClick={() => remove(member.user_id)}>Remove grant</button></div>)}</div></Modal>;
}
