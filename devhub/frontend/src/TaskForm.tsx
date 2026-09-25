import { useState, type FormEvent } from 'react';
import { LoaderCircle, Trash2 } from 'lucide-react';
import { messageOf, request } from './api';
import { Alert, Modal } from './ui';
import type { Member, Priority, Task, TaskStatus, User } from './types';

export const statuses: { value: TaskStatus; label: string; className: string }[] = [
  { value: 'todo', label: 'To do', className: 'todo' },
  { value: 'in_progress', label: 'In progress', className: 'progress' },
  { value: 'done', label: 'Done', className: 'done' },
];

export function TaskForm({ task, initialStatus = 'todo', path, csrf, members, user, canEdit, canDelete, onClose, onSaved }: {
  task?: Task; initialStatus?: TaskStatus; path: string; csrf: string | null; members: Member[]; user: User; canEdit: boolean; canDelete: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [title, setTitle] = useState(task?.title ?? '');
  const [description, setDescription] = useState(task?.description ?? '');
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? initialStatus);
  const [priority, setPriority] = useState<Priority>(task?.priority ?? 'medium');
  const [assignee, setAssignee] = useState(task?.assignee_id ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const eligibleMembers = members.length ? members.filter(member => member.active !== false) : [{ user_id: user.id, display_name: user.display_name, email: user.email }];
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await request(task ? `${path}/${task.id}` : path, { method: task ? 'PATCH' : 'POST', csrf, body: { title: title.trim(), description, status, priority, assignee_id: assignee || null, ...(task ? { version: task.version } : {}) } });
      onSaved(); onClose();
    } catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setError('');
    try { await request(`${path}/${task!.id}`, { method: 'DELETE', csrf }); onSaved(); onClose(); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  return <Modal title={task ? 'Task details' : 'Create a task'} onClose={onClose}>
    <form onSubmit={save} className="form-stack">
      {error && <Alert>{error}</Alert>}
      <label>Title<input autoFocus required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} placeholder="What needs to get done?" disabled={!canEdit || busy} /></label>
      <label>Description<textarea rows={5} maxLength={20000} value={description} onChange={event => setDescription(event.target.value)} placeholder="Add context, requirements, or a definition of done…" disabled={!canEdit || busy} /></label>
      <div className="form-row"><label>Status<select value={status} onChange={event => setStatus(event.target.value as TaskStatus)} disabled={!canEdit || busy}>{statuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Priority<select value={priority} onChange={event => setPriority(event.target.value as Priority)} disabled={!canEdit || busy}>{['low', 'medium', 'high', 'urgent'].map(value => <option value={value} key={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label></div>
      <label>Assignee<select value={assignee} onChange={event => setAssignee(event.target.value)} disabled={!canEdit || busy}><option value="">Unassigned</option>{eligibleMembers.map(member => <option key={member.user_id} value={member.user_id}>{member.display_name || member.email}{member.user_id === user.id ? ' (you)' : ''}</option>)}{assignee && !eligibleMembers.some(member => member.user_id === assignee) && <option value={assignee}>Current assignee</option>}</select></label>
      {members.length > 0 && <p className="field-hint">Assignees must also have access to this project.</p>}
      {confirmDelete && <div className="delete-confirm"><p>Delete this task? This cannot be undone.</p><button type="button" className="button danger" disabled={busy} onClick={remove}>Delete task</button><button type="button" className="button secondary" onClick={() => setConfirmDelete(false)}>Keep task</button></div>}
      <div className="modal-actions">{task && canDelete && !confirmDelete && <button className="icon-button danger-text" type="button" aria-label="Delete task" onClick={() => setConfirmDelete(true)}><Trash2 size={18} /></button>}<span className="spacer" /><button type="button" className="button secondary" onClick={onClose}>{canEdit ? 'Cancel' : 'Close'}</button>{canEdit && <button className="button primary" disabled={busy || !title.trim()}>{busy && <LoaderCircle size={16} className="spin" />}{task ? 'Save changes' : 'Create task'}</button>}</div>
    </form>
  </Modal>;
}
