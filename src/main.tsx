import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Code2,
  Copy,
  Download,
  Gauge,
  LayoutDashboard,
  Network,
  Play,
  Plus,
  RefreshCcw,
  Save,
  Search,
  Server,
  Square,
  TerminalSquare,
  Trash2,
} from 'lucide-react';
import './styles.css';

const API_BASE = '/api';

async function api(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const json = await res.json();
  if (json.code !== 0) throw new Error(json.message);
  return json.data;
}

type PageKey = 'dashboard' | 'apis' | 'servers' | 'tasks' | 'scripts';
type Method = 'GET' | 'POST';

interface ApiEndpoint {
  id: number; name: string; method: Method; host: string; path: string;
  headers: string; body: string; last_response: string;
}

interface SshServer {
  id: number; name: string; host: string; port: number;
  username: string; password?: string; work_dir?: string; env: string; status?: string;
}

interface ScriptFile {
  id: number; name: string; content: string; created_at: string;
}

interface LoadTask {
  id: number; name: string; script_file_id: number | null; server_id: number | null;
  target_host: string; users: number; spawn_rate: number; run_time: string;
  run_mode: string; web_port: number | null;
  status: string; remote_pid: number | null; error_message: string; report_path: string;
  created_at: string | null; started_at: string | null; finished_at: string | null;
}

interface PublicHost {
  id: number; name: string; url: string;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => { const t = setTimeout(() => setDebounced(value), delay); return () => clearTimeout(t); }, [value, delay]);
  return debounced;
}

const PAGE_SIZE = 10;

function App() {
  const [page, setPage] = useState<PageKey>('dashboard');
  const [apis, setApis] = useState<ApiEndpoint[]>([]);
  const [publicHosts, setPublicHosts] = useState<PublicHost[]>([
    { id: 1, name: '测试环境', url: 'https://api.example.com' },
  ]);
  const [servers, setServers] = useState<SshServer[]>([]);
  const [scriptFiles, setScriptFiles] = useState<ScriptFile[]>([]);
  const [tasks, setTasks] = useState<LoadTask[]>([]);
  const [editingApi, setEditingApi] = useState<ApiEndpoint | null>(null);
  const [editingServer, setEditingServer] = useState<SshServer | null>(null);
  const [editingTask, setEditingTask] = useState<LoadTask | null>(null);
  const [curlImportOpen, setCurlImportOpen] = useState(false);
  const [hostDialogOpen, setHostDialogOpen] = useState(false);
  const [curlPreview, setCurlPreview] = useState('');
  const [responsePreview, setResponsePreview] = useState<ApiEndpoint | null>(null);
  const [scriptContent, setScriptContent] = useState('');
  const [apiKeyword, setApiKeyword] = useState('');
  const [apiPage, setApiPage] = useState(1);
  const [serverConsole, setServerConsole] = useState<string[]>(['console ready']);
  const [selectedApiIds, setSelectedApiIds] = useState<number[]>([]);
  const [selectedTask, setSelectedTask] = useState<LoadTask | null>(null);
  const [taskLogs, setTaskLogs] = useState('');
  const [taskStats, setTaskStats] = useState<any>(null);

  const debouncedKeyword = useDebounce(apiKeyword, 300);
  useEffect(() => { setApiPage(1); }, [debouncedKeyword]);

  const filteredApis = useMemo(() => {
    const kw = debouncedKeyword.toLowerCase();
    if (!kw) return apis;
    return apis.filter((a) => a.name.toLowerCase().includes(kw) || `${a.host}${a.path}`.toLowerCase().includes(kw));
  }, [apis, debouncedKeyword]);
  const apiTotalPages = Math.max(1, Math.ceil(filteredApis.length / PAGE_SIZE));
  const pagedApis = filteredApis.slice((apiPage - 1) * PAGE_SIZE, apiPage * PAGE_SIZE);

  const runningCount = tasks.filter((t) => t.status === 'running').length;

  const load = useCallback(async () => {
    try {
      const [a, s, sc, t] = await Promise.all([
        api('/endpoints'),
        api('/servers'),
        api('/scripts'),
        api('/tasks'),
      ]);
      setApis(a.items);
      setServers(s.items);
      setScriptFiles(sc.items);
      setTasks(t.items);
      if (!selectedApiIds.length && a.items.length) {
        setSelectedApiIds(a.items.map((i: ApiEndpoint) => i.id));
      }
    } catch (e) {
      console.error(e);
    }
  }, [selectedApiIds.length]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [load]);

  const generateScript = useCallback(async () => {
    try {
      const data = await api('/scripts/generate', {
        method: 'POST',
        body: JSON.stringify({ endpoint_ids: selectedApiIds }),
      });
      setScriptContent(data.content);
    } catch (e) { console.error(e); }
  }, [selectedApiIds]);

  useEffect(() => { generateScript(); }, [generateScript]);

  const saveApi = async (body: any) => {
    if (body.id && body.id !== 0) {
      await api(`/endpoints/${body.id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      const { id, ...rest } = body;
      await api('/endpoints', { method: 'POST', body: JSON.stringify(rest) });
    }
    setEditingApi(null);
    load();
  };

  const deleteApi = async (id: number) => {
    await api(`/endpoints/${id}`, { method: 'DELETE' });
    load();
  };

  const testApi = async (id: number) => {
    const data = await api(`/endpoints/${id}/test`, { method: 'POST' });
    setResponsePreview(apis.find((a) => a.id === id) ?? null);
    load();
  };

  const saveServer = async (body: any) => {
    if (body.id && body.id !== 0) {
      await api(`/servers/${body.id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      const { id, ...rest } = body;
      await api('/servers', { method: 'POST', body: JSON.stringify(rest) });
    }
    setEditingServer(null);
    load();
  };

  const deleteServer = async (id: number) => {
    await api(`/servers/${id}`, { method: 'DELETE' });
    load();
  };

  const testServer = async (id: number) => {
    setServerConsole((l) => [...l, `testing server ${id}...`]);
    const data = await api(`/servers/${id}/test`, { method: 'POST' });
    setServerConsole((l) => [...l, data.success ? `connected: ${data.detail}` : `failed: ${data.error}`]);
    if (data.success) window.open(`ssh://${servers.find((s) => s.id === id)?.username}@${servers.find((s) => s.id === id)?.host}:${servers.find((s) => s.id === id)?.port}`, '_blank');
    load();
  };

  const saveScriptFile = async (): Promise<ScriptFile | null> => {
    if (!scriptContent.trim()) return null;
    const saved = await api('/scripts', {
      method: 'POST',
      body: JSON.stringify({ name: 'stress_test.py', content: scriptContent }),
    });
    await load();
    return saved;
  };

  const saveScriptAndCreateTask = async () => {
    const saved = await saveScriptFile();
    if (!saved) return;
    const defaultHost = apis.find((item) => selectedApiIds.includes(item.id))?.host ?? 'https://api.example.com';
    setEditingTask({ id: 0, name: `真实接口回测 ${new Date().toLocaleTimeString()}`, script_file_id: saved.id, server_id: null, target_host: defaultHost, users: 1, spawn_rate: 1, run_time: '10s', run_mode: 'web_ui', web_port: null, status: 'draft', remote_pid: null, error_message: '', report_path: '', created_at: null, started_at: null, finished_at: null });
    setPage('tasks');
  };

  const deleteScriptFile = async (id: number) => {
    await api(`/scripts/${id}`, { method: 'DELETE' });
    load();
  };

  const downloadScript = (name: string, content: string) => {
    const blob = new Blob([content], { type: 'text/x-python' });
    const url = URL.createObjectURL(blob);
    Object.assign(document.createElement('a'), { href: url, download: name }).click();
    URL.revokeObjectURL(url);
  };

  const saveTask = async (body: any) => {
    if (body.id && body.id !== 0) {
      await api(`/tasks/${body.id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      const { id, ...rest } = body;
      await api('/tasks', { method: 'POST', body: JSON.stringify(rest) });
    }
    setEditingTask(null);
    load();
  };

  const deleteTask = async (id: number) => {
    await api(`/tasks/${id}`, { method: 'DELETE' });
    load();
  };

  const startTask = async (id: number) => {
    await api(`/tasks/${id}/start`, { method: 'POST' });
    load();
  };

  const precheckTask = async (id: number) => {
    const data = await api(`/tasks/${id}/precheck`, { method: 'POST' });
    setTaskLogs(JSON.stringify(data, null, 2));
    setSelectedTask(tasks.find((task) => task.id === id) ?? null);
  };

  const viewTask = async (task: LoadTask) => {
    setSelectedTask(task);
    const [logs, stats] = await Promise.all([api(`/tasks/${task.id}/logs`), api(`/tasks/${task.id}/stats`)]);
    setTaskLogs(logs.content);
    setTaskStats(stats);
  };

  const stopTask = async (id: number) => {
    await api(`/tasks/${id}/stop`, { method: 'POST' });
    load();
  };

  const sshUrl = (s: SshServer) => `ssh://${s.username}@${s.host}:${s.port}`;
  const importCurl = async (curl: string) => {
    const api2 = parseCurl(curl, publicHosts[0]?.url ?? 'https://api.example.com');
    await api('/endpoints', { method: 'POST', body: JSON.stringify(api2) });
    setCurlImportOpen(false);
    load();
  };
  const showCurl = (a: ApiEndpoint) => setCurlPreview(toCurl(a));

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="brand"><Gauge /> LocustLab</div>
        <nav>
          <NavItem icon={<LayoutDashboard />} label="总览" active={page === 'dashboard'} onClick={() => setPage('dashboard')} />
          <NavItem icon={<Network />} label="接口管理" active={page === 'apis'} onClick={() => setPage('apis')} />
          <NavItem icon={<Server />} label="服务管理" active={page === 'servers'} onClick={() => setPage('servers')} />
          <NavItem icon={<Activity />} label="压测任务" active={page === 'tasks'} onClick={() => setPage('tasks')} />
          <NavItem icon={<Code2 />} label="脚本生成" active={page === 'scripts'} onClick={() => setPage('scripts')} />
        </nav>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <b>{pageTitle(page)}</b>
            <span>后端：FastAPI + SQLite + Paramiko</span>
          </div>
          <button onClick={() => setPage('tasks')}><Play size={16} /> 快速启动任务</button>
        </header>

        {page === 'dashboard' && (
          <section className="page-stack">
            <div className="stats-grid">
              <Stat icon={<Network />} label="接口数量" value={apis.length} />
              <Stat icon={<Server />} label="SSH 服务" value={servers.length} />
              <Stat icon={<Code2 />} label="脚本文件" value={scriptFiles.length} />
              <Stat icon={<Activity />} label="运行任务" value={runningCount} />
            </div>
          </section>
        )}

        {page === 'apis' && (
          <section className="page-stack">
            <Card title="接口管理" action={<div className="row-actions"><button onClick={() => setCurlImportOpen(true)}><Download size={16} /> 导入 curl</button><button onClick={() => setHostDialogOpen(true)}><Server size={16} /> 公共 Host</button><button onClick={() => setEditingApi({ id: 0, name: '', method: 'GET', host: publicHosts[0]?.url ?? 'https://api.example.com', path: '/api/new', headers: '{}', body: '{}', last_response: '' })}><Plus size={16} /> 新增接口</button></div>}>
              <div className="api-toolbar">
                <div className="search-box"><Search size={16} /><input placeholder="请输入关键字搜索，如接口名称、地址" value={apiKeyword} onChange={(e) => setApiKeyword(e.target.value)} /></div>
              </div>
              <DataTable headers={['名称', '方法', '地址', '操作']}>
                {pagedApis.map((a) => <tr key={a.id}><td>{a.name || '--'}</td><td><Badge tone={a.method === 'GET' ? 'cyan' : 'green'}>{a.method}</Badge></td><td className="mono api-address">{a.host}{a.path}</td><td className="row-actions"><button onClick={() => testApi(a.id)}><RefreshCcw size={14} /> 测试</button><button onClick={() => showCurl(a)}><Code2 size={14} /> curl</button><button onClick={() => setEditingApi(a)}><Save size={14} /> 编辑</button><button className="danger" onClick={() => deleteApi(a.id)}><Trash2 size={14} /> 删除</button></td></tr>)}
              </DataTable>
              {apiTotalPages > 1 && <div className="pagination"><button disabled={apiPage <= 1} onClick={() => setApiPage((p) => p - 1)}><ChevronLeft size={16} /> 上一页</button><span className="page-info">{apiPage} / {apiTotalPages}</span><button disabled={apiPage >= apiTotalPages} onClick={() => setApiPage((p) => p + 1)}>下一页 <ChevronRight size={16} /></button></div>}
            </Card>
          </section>
        )}

        {page === 'servers' && (
          <Card title="压测机管理" action={<button onClick={() => setEditingServer({ id: 0, name: '', host: '', port: 22, username: 'root', password: '', work_dir: '/opt/locust-platform', env: 'test' })}><Plus size={16} /> 新增压测机</button>}>
            <DataTable headers={['名称', 'Host', '用户', '环境', '操作']}>
              {servers.map((s) => <tr key={s.id}><td>{s.name}</td><td className="mono">{s.host}:{s.port}</td><td>{s.username}</td><td><Badge tone={s.env === 'prod' ? 'red' : s.env === 'staging' ? 'amber' : 'cyan'}>{s.env}</Badge></td><td className="row-actions"><a className="ssh-link" href={sshUrl(s)}><TerminalSquare size={14} /> 连接</a><button onClick={() => testServer(s.id)}><RefreshCcw size={14} /> 测试</button><button onClick={() => setEditingServer(s)}><Save size={14} /> 编辑</button><button className="danger" onClick={() => deleteServer(s.id)}><Trash2 size={14} /> 删除</button></td></tr>)}
            </DataTable>
            <div className="hint" style={{ marginTop: 12 }}>点击“连接”打开系统终端。点击“测试”会通过后端 Paramiko 连接并检查环境。</div>
          </Card>
        )}

        {page === 'tasks' && (
          <section className="page-stack">
          <Card title="压测任务" action={<button onClick={() => setEditingTask({ id: 0, name: '', script_file_id: scriptFiles[0]?.id ?? null, server_id: servers[0]?.id ?? null, target_host: apis[0]?.host ?? 'https://api.example.com', users: 1, spawn_rate: 1, run_time: '10s', run_mode: 'web_ui', web_port: null, status: 'draft', remote_pid: null, error_message: '', report_path: '', created_at: null, started_at: null, finished_at: null })}><Plus size={16} /> 新建任务</button>}>
            <DataTable headers={['任务名', '服务器', '目标 Host', '并发', '状态', '操作']}>
              {tasks.map((t) => <tr key={t.id}><td>{t.name}</td><td>{servers.find((s) => s.id === t.server_id)?.name ?? '本机执行'}</td><td>{t.target_host}</td><td>{t.users} / {t.spawn_rate}</td><td><Badge tone={t.status === 'running' ? 'green' : t.status === 'failed' ? 'red' : t.status === 'success' ? 'cyan' : 'muted'}>{t.status}</Badge></td><td className="row-actions"><button onClick={() => precheckTask(t.id)}><RefreshCcw size={14} /> 预检</button><button onClick={() => startTask(t.id)} disabled={t.status === 'running'}><Play size={14} /> 启动</button><button onClick={() => stopTask(t.id)} disabled={t.status !== 'running'}><Square size={14} /> 停止</button><button onClick={() => viewTask(t)}><TerminalSquare size={14} /> 详情</button><button onClick={() => setEditingTask(t)}><Save size={14} /> 编辑</button><button className="danger" onClick={() => deleteTask(t.id)}><Trash2 size={14} /> 删除</button></td></tr>)}
            </DataTable>
          </Card>
          {selectedTask && <Card title={`任务详情：${selectedTask.name}`} action={<div className="row-actions"><button onClick={() => viewTask(selectedTask)}><RefreshCcw size={14} /> 刷新</button><a className="ssh-link" target="_blank" href={`/api/tasks/${selectedTask.id}/report`}><Download size={14} /> 查看报告</a><a className="ssh-link" href={`/api/tasks/${selectedTask.id}/report/download`}><Download size={14} /> 下载报告</a></div>}>
            <div className="stats-grid task-detail-grid">
              <Stat icon={<Activity />} label="状态" value={selectedTask.status === 'success' ? 1 : selectedTask.status === 'running' ? 2 : 0} />
              <Stat icon={<Play />} label="远程/本机 PID" value={selectedTask.remote_pid ?? 0} />
              <Stat icon={<Gauge />} label="请求数" value={Number(taskStats?.summary?.['Request Count'] ?? 0)} />
              <Stat icon={<Trash2 />} label="失败数" value={Number(taskStats?.summary?.['Failure Count'] ?? 0)} />
            </div>
            {selectedTask.run_mode === 'web_ui' && selectedTask.web_port && selectedTask.status === 'running' && <div className="locust-frame-wrap">
              {(() => { const host = servers.find((s) => s.id === selectedTask.server_id)?.host ?? '127.0.0.1'; const url = `http://${host}:${selectedTask.web_port}`; return <><div className="hint">Locust 原生 Web UI：<a target="_blank" href={url}>{url}</a></div><iframe title="Locust Web UI" className="locust-frame" src={url} /></>; })()}
            </div>}
            <pre className="terminal task-log">{taskLogs || '暂无日志'}</pre>
          </Card>}
          </section>
        )}

        {page === 'scripts' && (
          <section className="page-stack">
            <Card title="Locust 脚本生成" action={<div className="row-actions"><button onClick={() => navigator.clipboard?.writeText(scriptContent)}><Copy size={16} /> 复制</button><button onClick={() => downloadScript('stress_test.py', scriptContent)}><Download size={16} /> 下载 .py</button><button onClick={() => saveScriptFile()}><Save size={16} /> 保存到后端</button><button onClick={() => saveScriptAndCreateTask()}><Play size={16} /> 保存并创建任务</button><button onClick={() => generateScript()}><RefreshCcw size={16} /> 重新生成</button></div>}>
              <div className="api-picker">
                {apis.map((a) => <label className="check-row" key={a.id}><input type="checkbox" checked={selectedApiIds.includes(a.id)} onChange={(e) => setSelectedApiIds((ids) => e.target.checked ? [...ids, a.id] : ids.filter((id) => id !== a.id))} /><span>{a.name || '--'}</span><small className="mono">{a.method} {a.path}</small></label>)}
              </div>
              <textarea className="code-editor" value={scriptContent} onChange={(e) => setScriptContent(e.target.value)} spellCheck={false} />
            </Card>
            {scriptFiles.length > 0 && <Card title="已保存脚本">
              <DataTable headers={['文件名', '保存时间', '操作']}>
                {scriptFiles.map((f) => <tr key={f.id}><td>{f.name}</td><td className="hint">{f.created_at}</td><td className="row-actions"><button onClick={() => navigator.clipboard?.writeText(f.content)}><Copy size={14} /> 复制</button><button onClick={() => downloadScript(f.name, f.content)}><Download size={14} /> 下载</button><button className="danger" onClick={() => deleteScriptFile(f.id)}><Trash2 size={14} /> 删除</button></td></tr>)}
              </DataTable>
            </Card>}
          </section>
        )}
      </main>

      {editingApi && <ApiDialog value={editingApi} hosts={publicHosts} onClose={() => setEditingApi(null)} onSave={(v) => saveApi(v)} />}
      {editingServer && <ServerDialog value={editingServer} onClose={() => setEditingServer(null)} onSave={(v) => saveServer(v)} />}
      {editingTask && <TaskDialog value={editingTask} scripts={scriptFiles} servers={servers} onClose={() => setEditingTask(null)} onSave={(v) => saveTask(v)} />}
      {curlImportOpen && <CurlImportDialog onClose={() => setCurlImportOpen(false)} onImport={importCurl} />}
      {hostDialogOpen && <HostDialog hosts={publicHosts} onSave={(h) => { setPublicHosts((items) => [...items.filter((i) => i.id !== h.id), { ...h, id: h.id || Date.now() }]); }} onDelete={(id) => setPublicHosts((items) => items.filter((i) => i.id !== id))} onClose={() => setHostDialogOpen(false)} />}
      {curlPreview && <CodeDialog title="导出 curl" code={curlPreview} onClose={() => setCurlPreview('')} />}
      {responsePreview && <ResponseDialog api={responsePreview} onClose={() => setResponsePreview(null)} />}
    </div>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return <button className={active ? 'active' : ''} onClick={onClick}>{icon}{label}</button>;
}
function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: number | string }) {
  return <div className="stat-card"><div>{icon}</div><span>{label}</span><b>{value}</b></div>;
}
function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return <section className="card"><header><h2>{title}</h2>{action}</header>{children}</section>;
}
function DataTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return <div className="table-wrap"><table><thead><tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
function Badge({ tone, children }: { tone: string; children: React.ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Terminal({ lines }: { lines: string[] }) {
  return <pre className="terminal">{lines.length ? lines.join('\n') : '暂无日志'}</pre>;
}
function Dialog({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return <div className="dialog-mask"><div className="dialog"><header><h2>{title}</h2><button onClick={onClose}>关闭</button></header>{children}</div></div>;
}
function FormGrid({ children }: { children: React.ReactNode }) {
  return <div className="form-grid">{children}</div>;
}
function Text({ label, value, placeholder, onChange }: { label: string; value: string; placeholder?: string; onChange: (v: string) => void }) {
  return <label><span>{label}</span><input placeholder={placeholder ?? `请输入${label}`} value={value} onChange={(e) => onChange(e.target.value)} /></label>;
}
function Select({ label, value, options, labelMap, onChange }: { label: string; value: string; options: string[]; labelMap?: (v: string) => string; onChange: (v: string) => void }) {
  return <label><span>{label}</span><select value={value} onChange={(e) => onChange(e.target.value)}>{options.map((o) => <option key={o} value={o}>{labelMap ? labelMap(o) : o}</option>)}</select></label>;
}
function Area({ label, value, placeholder, wide, onChange }: { label: string; value: string; placeholder?: string; wide?: boolean; onChange: (v: string) => void }) {
  return <label className={wide ? 'wide-field' : ''}><span>{label}</span><textarea placeholder={placeholder ?? `请输入${label}`} value={value} onChange={(e) => onChange(e.target.value)} /></label>;
}
function DialogFooter({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  return <footer className="dialog-footer"><button onClick={onClose}>取消</button><button className="primary" onClick={onSave}><Save size={16} /> 保存</button></footer>;
}

function ApiDialog({ value, hosts, onClose, onSave }: { value: ApiEndpoint; hosts: PublicHost[]; onClose: () => void; onSave: (v: any) => void }) {
  const [form, setForm] = useState(value);
  return <Dialog title={value.id ? '编辑接口' : '新增接口'} onClose={onClose}><FormGrid><Text label="名称" placeholder="请输入接口名称，如登录接口" value={form.name} onChange={(v) => setForm({ ...form, name: v })} /><Select label="方法" value={form.method} options={['GET', 'POST']} onChange={(v) => setForm({ ...form, method: v as Method })} /><HostInput label="Host" value={form.host} hosts={hosts} onChange={(v) => setForm({ ...form, host: v })} /><Text label="Path" placeholder="请输入接口路径，如 /api/auth/login" value={form.path} onChange={(v) => setForm({ ...form, path: v })} /><Area label="Headers JSON" placeholder='请输入请求头 JSON，如 {"Content-Type":"application/json"}' value={form.headers} onChange={(v) => setForm({ ...form, headers: v })} /><Area label="Body JSON" placeholder='请输入请求体 JSON，如 {"username":"demo"}' value={form.body} onChange={(v) => setForm({ ...form, body: v })} /></FormGrid><DialogFooter onClose={onClose} onSave={() => onSave(form)} /></Dialog>;
}

function HostInput({ label, value, hosts, onChange }: { label: string; value: string; hosts: PublicHost[]; onChange: (v: string) => void }) {
  const selected = hosts.find((h) => h.url === value)?.url ?? '';
  return <label><span>{label}</span><div className="host-input-row"><input placeholder="请输入 Host，如 https://api.example.com" value={value} onChange={(e) => onChange(e.target.value)} /><select value={selected} onChange={(e) => e.target.value && onChange(e.target.value)}><option value="">选择公共 Host</option>{hosts.map((h) => <option key={h.id} value={h.url}>{h.name}</option>)}</select></div></label>;
}

function ServerDialog({ value, onClose, onSave }: { value: SshServer; onClose: () => void; onSave: (v: any) => void }) {
  const [form, setForm] = useState(value);
  return <Dialog title={value.id ? '编辑压测机' : '新增压测机'} onClose={onClose}><FormGrid><Text label="名称" placeholder="请输入服务名称，如 locust-worker-01" value={form.name} onChange={(v) => setForm({ ...form, name: v })} /><Text label="Host" placeholder="请输入服务器 IP 或域名，如 10.8.0.31" value={form.host} onChange={(v) => setForm({ ...form, host: v })} /><Text label="端口" placeholder="请输入 SSH 端口，如 22" value={String(form.port)} onChange={(v) => setForm({ ...form, port: Number(v) || 22 })} /><Text label="用户名" placeholder="请输入 SSH 用户名，如 root" value={form.username} onChange={(v) => setForm({ ...form, username: v })} /><Text label="密码" placeholder="请输入 SSH 密码" value={form.password ?? ''} onChange={(v) => setForm({ ...form, password: v })} /><Text label="工作目录" placeholder="请输入远程工作目录，如 /opt/locust-platform" value={form.work_dir ?? '/opt/locust-platform'} onChange={(v) => setForm({ ...form, work_dir: v })} /><Select label="环境" value={form.env} options={['test', 'staging', 'prod']} onChange={(v) => setForm({ ...form, env: v })} /></FormGrid><DialogFooter onClose={onClose} onSave={() => onSave(form)} /></Dialog>;
}

function TaskDialog({ value, scripts, servers, onClose, onSave }: { value: LoadTask; scripts: ScriptFile[]; servers: SshServer[]; onClose: () => void; onSave: (v: any) => void }) {
  const [form, setForm] = useState(value);
  return <Dialog title={value.id ? '编辑压测任务' : '新建压测任务'} onClose={onClose}><FormGrid><Text label="任务名称" placeholder="请输入任务名称，如登录链路 100 并发" value={form.name} onChange={(v) => setForm({ ...form, name: v })} /><Select label="脚本文件" value={String(form.script_file_id ?? '')} options={scripts.map((s) => String(s.id))} labelMap={(id) => scripts.find((s) => s.id === Number(id))?.name ?? id} onChange={(v) => setForm({ ...form, script_file_id: Number(v) || null })} /><Select label="运行模式" value={form.run_mode ?? 'headless'} options={['web_ui', 'headless']} labelMap={(id) => id === 'web_ui' ? 'Locust Web UI（内嵌动态图）' : 'Headless（自动跑完出报告）'} onChange={(v) => setForm({ ...form, run_mode: v })} /><Select label="执行位置" value={String(form.server_id ?? '')} options={['', ...servers.map((s) => String(s.id))]} labelMap={(id) => id === '' ? '本机执行' : servers.find((s) => s.id === Number(id))?.name ?? id} onChange={(v) => setForm({ ...form, server_id: Number(v) || null })} /><Text label="目标 Host" placeholder="请输入压测目标 Host，如 https://api.example.com" value={form.target_host} onChange={(v) => setForm({ ...form, target_host: v })} /><Text label="并发用户" placeholder="请输入并发用户数，如 100" value={String(form.users)} onChange={(v) => setForm({ ...form, users: Number(v) || 1 })} /><Text label="启动速率" placeholder="请输入每秒启动用户数，如 10" value={String(form.spawn_rate)} onChange={(v) => setForm({ ...form, spawn_rate: Number(v) || 1 })} /><Text label="运行时长" placeholder="Headless 模式使用，如 10s / 5m" value={form.run_time} onChange={(v) => setForm({ ...form, run_time: v })} /></FormGrid><DialogFooter onClose={onClose} onSave={() => onSave(form)} /></Dialog>;
}

function CurlImportDialog({ onClose, onImport }: { onClose: () => void; onImport: (v: string) => void }) {
  const [curl, setCurl] = useState('');
  return <Dialog title="通过 curl 导入接口" onClose={onClose}><div className="single-field"><Area label="curl 命令" placeholder="请输入 curl 命令" value={curl} onChange={setCurl} wide /></div><p className="hint">支持 `-X`、`-H`、`-d/--data`、URL 解析。</p><DialogFooter onClose={onClose} onSave={() => onImport(curl)} /></Dialog>;
}

function HostDialog({ hosts, onSave, onDelete, onClose }: { hosts: PublicHost[]; onSave: (h: PublicHost) => void; onDelete: (id: number) => void; onClose: () => void }) {
  const [name, setName] = useState(''); const [url, setUrl] = useState(''); const [adding, setAdding] = useState(false);
  return <Dialog title="公共 Host" onClose={onClose}><div className="host-list">{hosts.map((h) => <div className="host-item" key={h.id}><div><b>{h.name}</b><span className="mono">{h.url}</span></div><button className="danger" onClick={() => onDelete(h.id)}><Trash2 size={14} /> 删除</button></div>)}{!hosts.length && <p className="hint">暂无公共 Host。</p>}</div>{adding && <div className="host-editor dialog-host-editor"><input placeholder="请输入 Host 名称，如测试环境" value={name} onChange={(e) => setName(e.target.value)} /><input placeholder="请输入 Host 地址，如 https://api.example.com" value={url} onChange={(e) => setUrl(e.target.value)} /><button className="primary" onClick={() => { if (!name.trim() || !url.trim()) return; onSave({ id: 0, name: name.trim(), url: url.trim().replace(/\/+$/, '') }); setName(''); setUrl(''); setAdding(false); }}><Save size={16} /> 保存</button></div>}<footer className="dialog-footer"><button onClick={() => setAdding(true)}><Plus size={16} /> 新增</button><button className="primary" onClick={onClose}>完成</button></footer></Dialog>;
}

function CodeDialog({ title, code, onClose }: { title: string; code: string; onClose: () => void }) {
  return <Dialog title={title} onClose={onClose}><pre className="code-block dialog-code">{code}</pre><footer className="dialog-footer"><button onClick={() => navigator.clipboard?.writeText(code)}>复制</button><button className="primary" onClick={onClose}>完成</button></footer></Dialog>;
}

function ResponseDialog({ api: a, onClose }: { api: ApiEndpoint; onClose: () => void }) {
  let parsed: any = {};
  try { parsed = JSON.parse(a.last_response); } catch {}
  const body = parsed.body !== undefined ? (typeof parsed.body === 'string' ? parsed.body : JSON.stringify(parsed.body, null, 2)) : a.last_response || '暂无响应，请先点击测试。';
  return <Dialog title={`测试响应：${a.name || '--'}`} onClose={onClose}><pre className="code-block dialog-code response-body">{body}</pre><footer className="dialog-footer"><button onClick={() => navigator.clipboard?.writeText(body)}>复制响应</button><button className="primary" onClick={onClose}>完成</button></footer></Dialog>;
}

function pageTitle(page: PageKey) {
  return { dashboard: '系统总览', apis: '接口管理', servers: '服务管理', tasks: '压测任务', scripts: '脚本生成' }[page];
}

function toCurl(a: ApiEndpoint) {
  let headers: Record<string, string> = {};
  try { headers = JSON.parse(a.headers); } catch {}
  const h = Object.entries(headers).map(([k, v]) => `  -H '${k}: ${v}' \\`).join('\n');
  const d = a.method === 'POST' && a.body && a.body !== '{}' ? `\n  -d '${a.body}'` : '';
  return [`curl -X ${a.method} '${a.host}${a.path}' \\`, h, d].filter(Boolean).join('\n');
}

function parseCurl(input: string, fallbackHost: string): any {
  const tokens: string[] = []; const pattern = /"([^"\\]*(?:\\.[^"\\]*)*)"|'([^']*)'|\S+/g; let m: RegExpExecArray | null;
  while ((m = pattern.exec(input.replace(/\\\n/g, ' ')))) tokens.push(m[1] ?? m[2] ?? m[0]);
  let method: Method = 'GET'; const headers: Record<string, string> = {}; let body = '{}'; let url = '';
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i]; const n = tokens[i + 1] ?? '';
    if (t === 'curl') continue;
    if (t === '-X' || t === '--request') { method = n.toUpperCase() === 'POST' ? 'POST' : 'GET'; i++; continue; }
    if (t === '-H' || t === '--header') { const p = n.indexOf(':'); if (p > -1) headers[n.slice(0, p).trim()] = n.slice(p + 1).trim(); i++; continue; }
    if (['-d', '--data', '--data-raw', '--data-binary'].includes(t)) { method = 'POST'; body = n || '{}'; i++; continue; }
    if (t === '-u' || t === '--user') { headers['Authorization'] = `Basic ${btoa(n)}`; i++; continue; }
    if (t === '--url') { url = n; i++; continue; }
    if (/^https?:\/\//.test(t)) url = t;
  }
  let host = fallbackHost.replace(/\/+$/, ''); let path = '/';
  try { const u = new URL(url); host = `${u.protocol}//${u.host}`; path = `${u.pathname}${u.search}`; } catch { path = url.startsWith('/') ? url : '/imported-api'; }
  return { name: '', method, host, path, headers: JSON.stringify(headers, null, 2), body: body || '{}', last_response: '' };
}

createRoot(document.getElementById('root')!).render(<App />);
