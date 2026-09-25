import { useState, type FormEvent } from 'react';
import { ArrowUpRight, CheckCircle2, GitBranch, Github, Info, LoaderCircle, Plus, RefreshCw, ShieldCheck } from 'lucide-react';
import { messageOf, request } from './api';
import { useResource } from './useResource';
import { Alert, dateLabel, Empty, Loading } from './ui';
import type { Installation, Organization, Page, Project, Repository, Session } from './types';

export function GitHubPanel({ org, project, projects = [], session }: { org: Organization; project?: Project; projects?: Project[]; session: Session }) {
  const [selectedId, setSelectedId] = useState(project?.id ?? projects[0]?.id ?? '');
  const projectId = project?.id ?? selectedId;
  const orgPath = `/api/v1/organizations/${org.id}`;
  const repositoryPath = projectId ? `${orgPath}/projects/${projectId}/repositories` : null;
  const installations = useResource<Page<Installation>>(`${orgPath}/github/installations`);
  const repositories = useResource<Page<Repository>>(repositoryPath ? `${repositoryPath}?limit=100` : null);
  const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false);
  const [showConnect, setShowConnect] = useState(false); const [showLink, setShowLink] = useState(false);
  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true); setError(''); setNotice('');
    try { await request(`${orgPath}/github/installations`, { method: 'POST', csrf: session.csrf_token, body: { installation_id: Number(data.get('installation_id')) } }); installations.reload(); setShowConnect(false); form.reset(); setNotice('GitHub installation verified and connected.'); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function link(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError(''); setNotice('');
    try { await request(repositoryPath!, { method: 'POST', csrf: session.csrf_token, body: { installation_id: Number(data.get('installation_id')), repository_id: Number(data.get('repository_id')) } }); repositories.reload(); setShowLink(false); setNotice('Repository linked. Metadata will appear after synchronization.'); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  async function sync(repository: Repository) {
    setBusy(true); setError(''); setNotice('');
    try { await request(`${repositoryPath}/${repository.id}/sync`, { method: 'POST', csrf: session.csrf_token }); repositories.reload(); setNotice(`Synchronization requested for ${repository.full_name}. Refresh the list to check progress.`); }
    catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); }
  }
  const enabled = installations.data?.items.filter(item => item.enabled !== false && item.verified !== false) ?? [];
  return <div className="integration-panel"><div className="integration-hero"><div className="github-logo"><Github size={32} /></div><div><div className="eyebrow">CONNECTED WORK</div><h2>A little closer to your code.</h2><p>Bring GitHub repository metadata into your team's workspace.</p></div><span className="badge purple"><ShieldCheck size={14} />Read-only integration</span></div>
    {(error || installations.error || repositories.error) && <Alert>{error || installations.error || repositories.error}</Alert>}
    {notice && <div className="notice" role="status"><CheckCircle2 size={18} />{notice}</div>}
    <section className="panel"><div className="panel-heading"><div><h3>GitHub installations</h3><p>Connections are visible to organization administrators.</p></div><button className="button secondary" onClick={() => setShowConnect(!showConnect)}><Plus size={16} />Connect installation</button></div>
      {installations.loading && !installations.data ? <Loading label="Loading GitHub connections…" /> : installations.data?.items.length ? <div className="installation-list">{installations.data.items.map(item => <div className="installation" key={item.installation_id}><Github size={22} /><div><strong>{item.account_login || item.account || `Installation ${item.installation_id}`}</strong><span>Installation #{item.installation_id}</span></div><span className={`badge ${item.enabled === false ? 'neutral' : 'green'}`}>{item.enabled === false ? 'Disabled' : item.verified === false ? 'Pending verification' : 'Connected'}</span></div>)}</div> : <div className="inline-empty"><Github size={20} /><p>No installation connected yet.</p></div>}
      {showConnect && <form className="setup-form form-stack" onSubmit={connect}><div className="info-block"><Info size={18} /><p>Install the configured DevHub GitHub App on your GitHub account first. Ask your DevHub operator to approve the installation for this organization, then enter its numeric installation ID. DevHub verifies the connection with GitHub.</p></div><label>GitHub installation ID<input type="number" name="installation_id" min="1" step="1" required placeholder="e.g. 12345678" /></label><div className="form-actions"><button className="button primary" disabled={busy}>{busy && <LoaderCircle size={16} className="spin" />}Verify and connect</button><button type="button" className="button secondary" onClick={() => setShowConnect(false)}>Cancel</button></div></form>}
    </section>
    <section className="panel"><div className="panel-heading"><div><h3>Linked repositories</h3><p>Repository details stay in sync through the background worker.</p></div><div className="toolbar-actions"><button className="icon-button" aria-label="Refresh repositories" disabled={!repositoryPath || repositories.loading} onClick={repositories.reload}><RefreshCw size={16} /></button><button className="button primary" disabled={!projectId || !enabled.length} onClick={() => setShowLink(!showLink)}><Plus size={16} />Link repository</button></div></div>
      {!project && projects.length > 0 && <div className="project-filter"><label>Project<select value={selectedId} onChange={event => { setSelectedId(event.target.value); setShowLink(false); }}>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>}
      {showLink && <form className="setup-form form-stack" onSubmit={link}><label>Installation<select name="installation_id" required>{enabled.map(item => <option value={item.installation_id} key={item.installation_id}>{item.account_login || item.account || `Installation ${item.installation_id}`}</option>)}</select></label><label>GitHub repository ID<input type="number" min="1" step="1" name="repository_id" required placeholder="Numeric ID of an installed repository" /></label><p className="field-hint">The repository must be accessible to this GitHub App installation. Find its numeric ID in the GitHub repository API response.</p><div className="form-actions"><button className="button primary" disabled={busy}>{busy && <LoaderCircle size={16} className="spin" />}Verify and link</button><button type="button" className="button secondary" onClick={() => setShowLink(false)}>Cancel</button></div></form>}
      {repositories.loading && !repositories.data ? <Loading label="Loading repositories…" /> : repositories.data?.items.length ? <div className="repository-list">{repositories.data.items.map(repository => <div className="repository" key={repository.id}><div className="repository-title"><GitBranch size={20} /><div><a href={safeGithubUrl(repository.html_url)} target="_blank" rel="noreferrer">{repository.full_name}<ArrowUpRight size={14} /></a><span>{repository.default_branch || 'Branch not synced'} · {repository.open_issues_count === null ? 'Issue count not synced' : `${repository.open_issues_count} open issues`}</span></div><button className="button secondary" disabled={busy} onClick={() => sync(repository)}><RefreshCw size={15} />Sync</button></div><div className="repository-footer"><span className="badge neutral">{repository.sync_state}</span><span>Last synced {dateLabel(repository.last_synced_at)}</span></div></div>)}</div> : <Empty icon={<GitBranch size={27} />} title={projectId ? 'Connect the work to the code' : 'Create a project first'}>{projectId ? 'Link a repository to see its latest metadata here.' : 'Repositories belong to a project. Add one to start connecting GitHub.'}</Empty>}
    </section></div>;
}

function safeGithubUrl(value: string) {
  try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === 'github.com' ? url.href : 'https://github.com'; } catch { return 'https://github.com'; }
}
