import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  CircleDollarSign,
  CircleStop,
  Clock3,
  CloudCog,
  Code2,
  Database,
  Eye,
  EyeOff,
  FileCode2,
  FileText,
  Globe2,
  Info,
  KeyRound,
  ListChecks,
  LoaderCircle,
  LockKeyhole,
  PackageOpen,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TerminalSquare,
  XCircle,
} from "lucide-react";
import { api, API_URL, errorMessage } from "../lib/api";
import { demoLogs, demoSettings, demoTasks } from "../lib/demo-data";
import { formatDate, statusLabel } from "../lib/format";
import type { AppSettings, AppSettingsUpdate, LogEntry, OzonCategory, TaskItem } from "../lib/types";
import { listItems } from "../lib/types";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, LoadingState, PageHeader, Select, cn } from "../components/ui";

type Notify = (message: string, tone?: "success" | "error" | "info") => void;

function taskTone(status?: string): "slate" | "blue" | "violet" | "emerald" | "amber" | "rose" {
  if (status === "running") return "violet";
  if (status === "success") return "emerald";
  if (status === "failed") return "rose";
  if (status === "cancelled") return "slate";
  return "amber";
}

export function TasksPage({ notify, onNavigateLogs }: { notify: Notify; onNavigateLogs: () => void }) {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [cancelling, setCancelling] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const result = await api.tasks({ status, task_type: type, limit: 100 }); setTasks(listItems(result)); setError(""); }
    catch (reason) { setTasks(demoTasks.filter((task) => (!status || task.status === status) && (!type || (task.task_type || task.type) === type))); setError(`本地服务暂未连接，当前显示预览数据。${errorMessage(reason)}`); }
    finally { setLoading(false); }
  }, [status, type]);
  useEffect(() => { void load(); }, [load]);

  async function cancel(task: TaskItem) {
    setCancelling(String(task.id));
    try { const updated = await api.cancelTask(task.id); setTasks((items) => items.map((item) => item.id === task.id ? updated : item)); notify("任务已取消", "success"); }
    catch (reason) { notify(errorMessage(reason), "error"); }
    finally { setCancelling(null); }
  }

  const taskTypes = Array.from(new Set(tasks.map((task) => task.task_type || task.type).filter((value): value is string => Boolean(value))));
  return <div><PageHeader eyebrow="Task history" title="任务中心" description="统一记录采集、AI 加工和 Ozon 操作的执行状态、进度与错误，便于追踪完整流程。" actions={<Button variant="secondary" onClick={() => void load()}><RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />刷新状态</Button>} />
    <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[
      { label: "运行中", count: tasks.filter((task) => task.status === "running").length, icon: LoaderCircle, color: "violet" }, { label: "等待中", count: tasks.filter((task) => task.status === "pending").length, icon: Clock3, color: "amber" }, { label: "已成功", count: tasks.filter((task) => task.status === "success").length, icon: CheckCircle2, color: "emerald" }, { label: "失败", count: tasks.filter((task) => task.status === "failed").length, icon: XCircle, color: "rose" },
    ].map((item) => { const Icon = item.icon; return <Card key={item.label} className="flex items-center gap-4 p-4"><span className={cn("grid h-10 w-10 place-items-center rounded-xl", item.color === "violet" ? "bg-violet-50 text-violet-600 dark:bg-violet-500/10" : item.color === "amber" ? "bg-amber-50 text-amber-600 dark:bg-amber-500/10" : item.color === "emerald" ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10" : "bg-rose-50 text-rose-600 dark:bg-rose-500/10")}><Icon className={cn("h-[18px] w-[18px]", item.label === "运行中" && "animate-spin")} /></span><div><p className="text-xl font-bold text-slate-950 dark:text-white">{item.count}</p><p className="text-xs text-slate-400">{item.label}</p></div></Card>; })}</div>
    {error && <div className="mb-4"><ErrorBanner compact message={error} onRetry={() => void load()} /></div>}
    <Card className="overflow-hidden"><div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-4 dark:border-slate-800"><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">全部任务状态</option><option value="running">运行中</option><option value="pending">等待中</option><option value="success">成功</option><option value="failed">失败</option><option value="cancelled">已取消</option></Select><Select value={type} onChange={(event) => setType(event.target.value)}><option value="">全部任务类型</option>{taskTypes.map((item) => <option key={item} value={item}>{item}</option>)}</Select><span className="ml-auto text-xs text-slate-400">显示最近 {tasks.length} 条任务</span></div><div className="app-scrollbar overflow-x-auto"><div className="min-w-[880px]"><div className="table-row-tasks border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:border-slate-800 dark:bg-slate-950/40"><div>任务</div><div>状态</div><div>进度</div><div>重试</div><div>开始时间</div><div className="text-right">操作</div></div>
      {loading && tasks.length === 0 ? <div className="p-5"><LoadingState label="正在读取任务记录" /></div> : tasks.length === 0 ? <div className="p-5"><EmptyState title="暂无任务记录" description="采集或处理一个商品后，任务记录会显示在这里。" /></div> : tasks.map((task) => { const progress = Math.max(0, Math.min(100, task.progress || 0)); const canCancel = task.status === "running" || task.status === "pending"; return <div key={task.id} className="table-row-tasks border-b border-slate-100 px-4 py-3.5 text-xs last:border-0 dark:border-slate-800"><div className="flex items-center gap-3"><span className={cn("grid h-9 w-9 place-items-center rounded-xl", task.status === "failed" ? "bg-rose-50 text-rose-600 dark:bg-rose-500/10" : "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10")}><ListChecks className="h-4 w-4" /></span><div><p className="font-semibold text-slate-800 dark:text-slate-100">{task.task_type || task.type || "流程任务"}</p><p className="mt-0.5 text-[10px] text-slate-400">#{task.id}{task.message ? ` · ${task.message}` : ""}</p>{task.error && <p className="mt-1 max-w-80 truncate text-[10px] text-rose-500" title={task.error}>{task.error}</p>}</div></div><div><Badge tone={taskTone(task.status)}>{task.status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}{statusLabel(task.status)}</Badge></div><div className="pr-5"><div className="mb-1.5 flex justify-between text-[10px] text-slate-400"><span>{task.status === "running" ? "处理中" : statusLabel(task.status)}</span><span>{progress}%</span></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className={cn("h-full rounded-full transition-all", task.status === "failed" ? "bg-rose-500" : task.status === "success" ? "bg-emerald-500" : "bg-indigo-500")} style={{ width: `${progress}%` }} /></div></div><div className="text-slate-500">{task.retries || 0} 次</div><div className="text-slate-500">{formatDate(task.started_at || task.created_at)}</div><div className="flex justify-end">{canCancel ? <Button size="sm" variant="ghost" className="text-slate-500 hover:text-rose-600" disabled={cancelling === String(task.id)} onClick={() => void cancel(task)}>{cancelling === String(task.id) ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <CircleStop className="h-3.5 w-3.5" />}取消</Button> : task.status === "failed" ? <Button size="sm" variant="ghost" onClick={onNavigateLogs}>查看日志<ArrowRight className="h-3.5 w-3.5" /></Button> : <span className="pr-3 text-[11px] text-slate-400">已记录</span>}</div></div>; })}</div></div></Card>
  </div>;
}

function levelTone(level: string): "blue" | "amber" | "rose" { return level === "ERROR" ? "rose" : level === "WARNING" ? "amber" : "blue"; }

export function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [level, setLevel] = useState("");
  const [module, setModule] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try { const result = await api.logs({ level, module, limit: 200 }); setLogs(listItems(result)); setError(""); }
    catch (reason) { setLogs(demoLogs.filter((log) => (!level || log.level === level) && (!module || log.module === module))); setError(`本地服务暂未连接，当前显示预览数据。${errorMessage(reason)}`); }
    finally { setLoading(false); }
  }, [level, module]);
  useEffect(() => { void load(); }, [load]);
  const visible = useMemo(() => logs.filter((log) => !search || log.message.toLowerCase().includes(search.toLowerCase())), [logs, search]);
  const modules = Array.from(new Set(logs.map((log) => log.module).filter((value): value is string => Boolean(value))));

  return <div><PageHeader eyebrow="Observability" title="运行日志" description="查看采集、AI、Ozon、数据库和任务模块的运行记录；敏感凭证会在日志层自动过滤。" actions={<Button variant="secondary" onClick={() => void load()}><RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />刷新日志</Button>} />{error && <div className="mb-4"><ErrorBanner compact message={error} onRetry={() => void load()} /></div>}<Card className="overflow-hidden"><div className="flex flex-col gap-2 border-b border-slate-100 p-4 dark:border-slate-800 lg:flex-row"><div className="relative flex-1"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-10" placeholder="搜索日志消息" value={search} onChange={(event) => setSearch(event.target.value)} /></div><Select value={level} onChange={(event) => setLevel(event.target.value)}><option value="">全部级别</option><option value="INFO">INFO</option><option value="WARNING">WARNING</option><option value="ERROR">ERROR</option></Select><Select value={module} onChange={(event) => setModule(event.target.value)}><option value="">全部模块</option>{modules.map((item) => <option value={item} key={item}>{item}</option>)}</Select></div>{loading && logs.length === 0 ? <div className="p-5"><LoadingState label="正在加载日志" /></div> : visible.length === 0 ? <div className="p-5"><EmptyState title="没有匹配的日志" description="调整筛选条件后重试。" /></div> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{visible.map((log) => <div key={log.id} className="grid gap-3 px-4 py-3 text-xs hover:bg-slate-50/70 dark:hover:bg-slate-800/30 sm:grid-cols-[96px_90px_140px_1fr] sm:items-start"><div className="pt-0.5 text-[11px] tabular-nums text-slate-400">{formatDate(log.created_at)}</div><div><Badge tone={levelTone(log.level)}>{log.level}</Badge></div><div className="flex items-center gap-2 font-semibold text-slate-600 dark:text-slate-300"><TerminalSquare className="h-3.5 w-3.5 text-slate-400" />{log.module || "系统"}</div><p className="break-words leading-5 text-slate-600 dark:text-slate-300">{log.message}</p></div>)}</div>}<div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-[11px] text-slate-400 dark:border-slate-800"><span>已过滤 API Key、Token 和密码等敏感字段</span><span>{visible.length} 条记录</span></div></Card></div>;
}

type SettingTab = "ozon" | "ai" | "source" | "pricing" | "system";

export function SettingsPage({ notify }: { notify: Notify }) {
  const [settings, setSettings] = useState<AppSettings>(demoSettings);
  const [tab, setTab] = useState<SettingTab>("ozon");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ozonClientId, setOzonClientId] = useState("");
  const [ozonKey, setOzonKey] = useState("");
  const [aiKey, setAiKey] = useState("");
  const [showOzonKey, setShowOzonKey] = useState(false);
  const [showAiKey, setShowAiKey] = useState(false);
  const [checkingAi, setCheckingAi] = useState(false);
  const [aiCheckMessage, setAiCheckMessage] = useState("");
  const [checkingOzon, setCheckingOzon] = useState(false);
  const [ozonCheckMessage, setOzonCheckMessage] = useState("");
  const [syncingCategories, setSyncingCategories] = useState(false);
  const [categoryQuery, setCategoryQuery] = useState("");
  const [categoryResults, setCategoryResults] = useState<OzonCategory[]>([]);
  const [categoryMessage, setCategoryMessage] = useState("");
  const [openingSourceBrowser, setOpeningSourceBrowser] = useState(false);
  const [sourceBrowserMessage, setSourceBrowserMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try { setSettings(await api.settings()); setError(""); }
    catch (reason) { setSettings(demoSettings); setError(`本地服务暂未连接，当前显示预览设置。${errorMessage(reason)}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  function applyDeepSeekPreset() {
    update("ai_provider", "openai_compatible");
    update("ai_base_url", "https://api.deepseek.com");
    update("ai_model", "deepseek-chat");
    setAiCheckMessage("");
    notify("已填入 DeepSeek 预设，输入 API Key 后保存并测试连接", "info");
  }

  async function testAiConnection() {
    setCheckingAi(true);
    setAiCheckMessage("");
    try {
      const result = await api.checkAiConnection({
        base_url: settings.ai_base_url || null,
        api_key: aiKey || undefined,
        model: settings.ai_model || null,
      });
      const verified = result.verified
        ? `，服务端返回 ${result.models.length} 个可用模型`
        : "（该网关未提供模型列表，仅验证连通性）";
      setAiCheckMessage(`连接成功：${result.base_url} / ${result.model}${verified}`);
      notify("AI 连接测试成功", "success");
    }
    catch (reason) { const message = `连接失败：${errorMessage(reason)}`; setAiCheckMessage(message); notify(message, "error"); }
    finally { setCheckingAi(false); }
  }

  async function testOzonConnection() {
    setCheckingOzon(true);
    setOzonCheckMessage("");
    try {
      const result = await api.checkOzonConnection({
        ...(ozonClientId ? { client_id: ozonClientId } : {}),
        ...(ozonKey ? { api_key: ozonKey } : {}),
      });
      const message = `连接成功：Ozon Seller API 可达（返回 ${result.items_returned} 个商品用于校验）`;
      setOzonCheckMessage(message);
      notify("Ozon 连接测试成功", "success");
    }
    catch (reason) { const message = `连接失败：${errorMessage(reason)}`; setOzonCheckMessage(message); notify(message, "error"); }
    finally { setCheckingOzon(false); }
  }

  async function syncOzonCategories() {
    setSyncingCategories(true);
    setCategoryMessage("");
    try {
      const result = await api.syncOzonCategories();
      setCategoryMessage(`类目树同步完成：${result.categories} 个类目已缓存到本地`);
      notify("Ozon 类目同步完成", "success");
    }
    catch (reason) { const message = `同步失败：${errorMessage(reason)}`; setCategoryMessage(message); notify(message, "error"); }
    finally { setSyncingCategories(false); }
  }

  async function searchOzonCategories() {
    const query = categoryQuery.trim();
    if (!query) { setCategoryResults([]); return; }
    try {
      setCategoryResults(await api.searchOzonCategories(query));
      setCategoryMessage("");
    }
    catch (reason) { setCategoryMessage(`搜索失败：${errorMessage(reason)}`); }
  }

  async function openSourceBrowser() {
    setOpeningSourceBrowser(true);
    try {
      const result = await api.openSourceBrowser();
      setSourceBrowserMessage(result.message);
      notify(result.message, "info");
    } catch (reason) { notify(errorMessage(reason), "error"); }
    finally { setOpeningSourceBrowser(false); }
  }

  function update(key: keyof AppSettings, value: unknown) { setSettings((current) => ({ ...current, [key]: value })); }
  async function save() {
    setSaving(true);
    try {
      const payload: AppSettingsUpdate = {
        source_provider: settings.source_provider,
        ai_provider: settings.ai_provider,
        ai_model: settings.ai_model,
        ai_temperature: settings.ai_temperature,
        ai_base_url: settings.ai_base_url || null,
        ozon_mode: settings.ozon_mode,
        exchange_rate: settings.exchange_rate,
        domestic_shipping: settings.domestic_shipping,
        international_shipping: settings.international_shipping,
        ozon_commission_rate: settings.ozon_commission_rate,
        target_margin: settings.target_margin,
        ...(ozonClientId ? { ozon_client_id: ozonClientId } : {}),
        ...(ozonKey ? { ozon_api_key: ozonKey } : {}),
        ...(aiKey ? { ai_api_key: aiKey } : {}),
      };
      const result = await api.updateSettings(payload);
      setSettings(result);
      setOzonClientId("");
      setOzonKey("");
      setAiKey("");
      notify("设置已安全保存", "success");
    }
    catch (reason) { notify(errorMessage(reason), "error"); }
    finally { setSaving(false); }
  }

  const tabs = [
    { id: "ozon" as const, label: "Ozon API", description: "认证与发布模式", icon: CloudCog }, { id: "ai" as const, label: "AI 模型", description: "Provider 与模型参数", icon: Sparkles }, { id: "source" as const, label: "1688 数据源", description: "采集 Provider", icon: Globe2 }, { id: "pricing" as const, label: "定价规则", description: "成本与利润参数", icon: CircleDollarSign }, { id: "system" as const, label: "系统", description: "本地服务与外观", icon: Settings2 },
  ];
  return <div><PageHeader eyebrow="Configuration" title="设置" description="管理外部服务、模型和业务参数。凭证不会写入源码，也不会出现在运行日志中。" actions={<Button disabled={saving || loading} onClick={() => void save()}>{saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存设置</Button>} />{error && <div className="mb-4"><ErrorBanner compact message={error} onRetry={() => void load()} /></div>}<div className="grid gap-5 lg:grid-cols-[250px_minmax(0,1fr)]"><Card className="h-fit p-2">{tabs.map((item) => { const Icon = item.icon; return <button key={item.id} onClick={() => setTab(item.id)} className={cn("flex w-full items-center gap-3 rounded-xl p-3 text-left transition", tab === item.id ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300" : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50")}><span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", tab === item.id ? "bg-white text-indigo-600 shadow-sm dark:bg-indigo-500/15 dark:text-indigo-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800")}><Icon className="h-4 w-4" /></span><span><strong className="block text-xs font-semibold">{item.label}</strong><span className="mt-0.5 block text-[10px] text-slate-400">{item.description}</span></span></button>; })}</Card><Card className="p-5 sm:p-6">{loading ? <LoadingState label="正在加载本地设置" /> : <>
      {tab === "ozon" && <SettingsSection icon={CloudCog} title="Ozon API" description="第一阶段默认使用 Mock Connector，切换真实模式前请完整测试商品审核流程。"><div className="grid gap-5 sm:grid-cols-2"><Field label="Client ID" hint={settings.ozon_client_id_configured ? "已配置" : "未配置"}><Input value={ozonClientId} onChange={(event) => setOzonClientId(event.target.value)} placeholder={settings.ozon_client_id_configured ? "已配置，输入新值可替换" : "输入 Ozon Client ID"} /></Field><Field label="API Key" hint={settings.ozon_api_key_configured ? "已配置" : "未配置"}><div className="relative"><Input className="pr-10" type={showOzonKey ? "text" : "password"} value={ozonKey} onChange={(event) => setOzonKey(event.target.value)} placeholder={settings.ozon_api_key_configured ? "••••••••••••••••" : "输入 Ozon API Key"} /><button aria-label={showOzonKey ? "隐藏 Ozon API Key" : "显示 Ozon API Key"} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" onClick={() => setShowOzonKey((value) => !value)} type="button">{showOzonKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></Field></div><Field label="发布连接器" className="mt-5"><Select className="w-full" value={settings.ozon_mode} onChange={(event) => update("ozon_mode", event.target.value)}><option value="mock">Mock（安全演示）</option><option value="real">真实 Ozon API</option></Select></Field><div className="mt-4 flex flex-wrap items-center gap-3"><Button variant="secondary" size="sm" disabled={checkingOzon} onClick={() => void testOzonConnection()}>{checkingOzon ? "测试中…" : "测试连接"}</Button>{ozonCheckMessage && <span className={cn("text-xs", ozonCheckMessage.startsWith("连接成功") ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300")}>{ozonCheckMessage}</span>}</div><p className="mt-2 text-[11px] leading-5 text-slate-400">未保存的新凭据会优先用于本次测试；留空则使用已保存的配置。</p><div className="mt-5 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs leading-5 text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" /><span>发布、批量改价与库存修改等高风险操作始终需要人工确认。{settings.ozon_mode === "real" ? "当前为真实模式：发布会调用 Ozon Seller API 并产生真实商品，请先用测试商品验证。" : "当前 Mock 模式不会修改真实店铺。"}</span></div><div className="mt-6 border-t border-slate-100 pt-6 dark:border-slate-800"><h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">类目与属性</h3><p className="mt-1 text-xs leading-5 text-slate-400">同步 Ozon 官方类目树到本地缓存，发布时用于校验必填属性。需要先配置有效的 API 凭据。</p><div className="mt-4 flex flex-wrap items-center gap-3"><Button variant="secondary" size="sm" disabled={syncingCategories} onClick={() => void syncOzonCategories()}>{syncingCategories ? "同步中…" : "同步类目树"}</Button><div className="relative min-w-[220px] flex-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-9" placeholder="搜索本地类目，例如 连衣裙" value={categoryQuery} onChange={(event) => setCategoryQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void searchOzonCategories(); }} /></div><Button variant="secondary" size="sm" onClick={() => void searchOzonCategories()}>搜索</Button></div>{categoryMessage && <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{categoryMessage}</p>}{categoryResults.length > 0 && <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">{categoryResults.map((category) => <div key={category.category_id} className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2.5 text-xs last:border-0 dark:border-slate-800"><div className="min-w-0"><p className="truncate font-semibold text-slate-700 dark:text-slate-200">{category.name}</p><p className="mt-0.5 text-[10px] text-slate-400">ID {category.category_id}{category.parent_category_id ? ` · 上级 ${category.parent_category_id}` : ""}</p></div><Button size="sm" variant="ghost" disabled={syncingCategories} onClick={() => void (async () => { try { const result = await api.syncOzonCategoryAttributes(category.category_id); notify(`类目 ${category.name} 属性同步完成：${result.attributes} 个（必填 ${result.required} 个）`, "success"); } catch (reason) { notify(errorMessage(reason), "error"); } })()}>同步属性</Button></div>)}</div>}</div></SettingsSection>}
      {tab === "ai" && <SettingsSection icon={Bot} title="AI Gateway" description="统一模型接口：Mock AI 用于演示，OpenAI Compatible 可接入 DeepSeek 等真实模型。"><div className="grid gap-5 sm:grid-cols-2"><Field label="Provider"><Select className="w-full" value={settings.ai_provider} onChange={(event) => update("ai_provider", event.target.value)}><option value="mock">Mock AI</option><option value="openai_compatible">OpenAI Compatible（含 DeepSeek）</option><option value="openai" disabled>OpenAI（开发中）</option><option value="anthropic" disabled>Anthropic（开发中）</option><option value="gemini" disabled>Gemini（开发中）</option></Select></Field><Field label="Model"><Input value={settings.ai_model} onChange={(event) => update("ai_model", event.target.value)} placeholder="模型名称" /></Field><Field label="Base URL"><Input value={settings.ai_base_url || ""} onChange={(event) => update("ai_base_url", event.target.value || null)} placeholder="使用 Provider 默认地址" /></Field><Field label="API Key" hint={settings.ai_api_key_configured ? "已配置" : "未配置"}><div className="relative"><Input className="pr-10" type={showAiKey ? "text" : "password"} value={aiKey} onChange={(event) => setAiKey(event.target.value)} placeholder={settings.ai_api_key_configured ? "••••••••••••••••" : "输入 AI API Key"} /><button aria-label={showAiKey ? "隐藏 AI API Key" : "显示 AI API Key"} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" onClick={() => setShowAiKey((value) => !value)} type="button">{showAiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></Field><Field label="Temperature" hint="建议 0–0.4"><Input type="number" min="0" max="2" step="0.1" value={settings.ai_temperature} onChange={(event) => update("ai_temperature", Number(event.target.value))} /></Field></div><div className="mt-5 flex items-start gap-3 rounded-xl bg-violet-50 p-4 text-xs leading-5 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300"><FileCode2 className="mt-0.5 h-4 w-4 shrink-0" /><span>真实 AI 通过 OpenAI Compatible 接口调用，商品加工使用 JSON 结构化输出。DeepSeek 的 deepseek-chat 支持 JSON 模式；deepseek-reasoner 会自动降级为文本解析。真实商品加工需要真实 AI，Mock AI 仍会被阻止用于真实商品。</span></div><div className="mt-4 flex flex-wrap items-center gap-3"><Button disabled={checkingAi} onClick={() => applyDeepSeekPreset()} variant="secondary">填入 DeepSeek 预设</Button><Button disabled={checkingAi} onClick={() => void testAiConnection()}>{checkingAi ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}测试连接</Button>{aiCheckMessage && <span className="text-xs text-slate-500 dark:text-slate-400">{aiCheckMessage}</span>}</div></SettingsSection>}
      {tab === "source" && <SettingsSection icon={Globe2} title="1688 数据源" description="真实采集使用独立的本地浏览器会话，读取你输入的商品页面。">
        <Field label="数据源配置"><Select className="w-full" value={settings.source_provider} onChange={(event) => update("source_provider", event.target.value)}><option value="browser">真实网页采集（本地浏览器）</option><option value="mock">固定模拟样例（仅演示）</option><option value="official" disabled>1688 官方 API（尚未接入）</option></Select></Field>
        <Field label="采集浏览器" hint="找不到时会自动换下一个" className="mt-5"><Select className="w-full" value={settings.source_browser_channel} onChange={(event) => update("source_browser_channel", event.target.value)}><option value="chrome">Google Chrome</option><option value="msedge">Microsoft Edge</option></Select></Field>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">{[{ icon: PackageOpen, label: "商品标题 / 图片", value: "读取实际商品页面" }, { icon: SlidersHorizontal, label: "SKU / 属性", value: "以页面提供的信息为准" }, { icon: FileText, label: "登录 / 验证", value: "需要时手动完成" }].map((item) => { const Icon = item.icon; return <div key={item.label} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><Icon className="h-4 w-4 text-indigo-500" /><p className="mt-4 text-xs font-semibold text-slate-700 dark:text-slate-200">{item.label}</p><p className="mt-1 text-[10px] leading-5 text-slate-500 dark:text-slate-400">{item.value}</p></div>; })}</div>
        <div className="mt-5 flex items-start gap-3 rounded-xl bg-blue-50 p-4 text-xs leading-5 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"><Info className="mt-0.5 h-4 w-4 shrink-0" /><span>商品采集页始终使用真实采集。遇到登录或验证时，在专用浏览器中完成后重试。读取失败会显示原因，不会替换成模拟商品。</span></div>
        {settings.source_provider === "mock" && <div className="mt-4"><ErrorBanner message="模拟样例为固定收纳盒，标题、图片、SKU、价格和库存均为虚构，与输入的 URL 无关。此配置不会让商品采集页自动切换为模拟采集。" /></div>}
        <div className="mt-5"><Button variant="secondary" disabled={openingSourceBrowser} onClick={() => void openSourceBrowser()}>{openingSourceBrowser ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Globe2 className="h-4 w-4" />}{openingSourceBrowser ? "正在打开" : "打开 1688 登录浏览器"}</Button><p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">浏览器会话在本地保存；打开浏览器不代表已经登录成功。{sourceBrowserMessage && <span className="mt-1 block">{sourceBrowserMessage}</span>}</p></div>
      </SettingsSection>}
      {tab === "pricing" && <SettingsSection icon={CircleDollarSign} title="定价规则" description="所有金额由确定性代码计算，AI 不参与数学运算。"><div className="grid gap-5 sm:grid-cols-2"><NumberSetting label="CNY → RUB 汇率" value={Number(settings.exchange_rate ?? 12.6)} suffix="RUB" onChange={(value) => update("exchange_rate", value)} /><NumberSetting label="国内物流" value={Number(settings.domestic_shipping ?? 5)} suffix="CNY" onChange={(value) => update("domestic_shipping", value)} /><NumberSetting label="国际物流预估" value={Number(settings.international_shipping ?? 28)} suffix="CNY" onChange={(value) => update("international_shipping", value)} /><NumberSetting label="Ozon 佣金" value={Number(settings.ozon_commission_rate ?? 18)} suffix="%" onChange={(value) => update("ozon_commission_rate", value)} /><NumberSetting label="目标利润率" value={Number(settings.target_margin ?? 30)} suffix="%" onChange={(value) => update("target_margin", value)} /></div><div className="mt-6 rounded-xl border border-slate-200 p-4 dark:border-slate-700"><h3 className="text-xs font-bold text-slate-700 dark:text-slate-200">计算项</h3><div className="mt-3 flex flex-wrap gap-2">{["采购价", "国内物流", "国际物流", "平台佣金", "广告成本", "退货损耗", "汇率", "目标利润"].map((item) => <Badge key={item}>{item}</Badge>)}</div></div></SettingsSection>}
      {tab === "system" && <SettingsSection icon={Settings2} title="系统设置" description="本地服务连接与数据存储信息。"><div className="space-y-3">{[{ icon: Code2, label: "本地 API 地址", value: API_URL }, { icon: Database, label: "数据存储", value: `${settings.database_backend === "sqlite" ? "SQLite" : settings.database_backend} · 本地工作空间` }, { icon: LockKeyhole, label: "运行模式", value: "单用户 · 无需登录" }].map((item) => { const Icon = item.icon; return <div key={item.label} className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700"><span className="grid h-9 w-9 place-items-center rounded-lg bg-slate-50 text-slate-500 dark:bg-slate-800"><Icon className="h-4 w-4" /></span><div className="min-w-0 flex-1"><p className="text-xs font-semibold text-slate-700 dark:text-slate-200">{item.label}</p><p className="mt-0.5 truncate font-mono text-[10px] text-slate-400">{item.value}</p></div><CheckCircle2 className="h-4 w-4 text-emerald-500" /></div>; })}</div><div className="mt-6 flex items-start gap-3 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600 dark:bg-slate-800/50 dark:text-slate-300"><KeyRound className="mt-0.5 h-4 w-4 shrink-0" /><span>密钥通过后端安全配置保存。界面只显示是否已配置，不会读回或展示完整密钥。</span></div></SettingsSection>}
    </>}</Card></div></div>;
}

function SettingsSection({ icon: Icon, title, description, children }: { icon: typeof Settings2; title: string; description: string; children: React.ReactNode }) {
  return <div><div className="mb-6 flex items-center gap-3 border-b border-slate-100 pb-5 dark:border-slate-800"><span className="grid h-11 w-11 place-items-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300"><Icon className="h-5 w-5" /></span><div><h2 className="text-base font-bold text-slate-900 dark:text-white">{title}</h2><p className="mt-0.5 text-xs text-slate-400">{description}</p></div></div>{children}</div>;
}

function NumberSetting({ label, value, suffix, onChange }: { label: string; value: number; suffix: string; onChange: (value: number) => void }) {
  return <Field label={label}><div className="relative"><Input className="pr-14" type="number" min="0" step="0.1" value={value} onChange={(event) => onChange(Number(event.target.value))} /><span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-slate-400">{suffix}</span></div></Field>;
}

export function ComingSoonPage({ label, onBack }: { label: string; onBack: () => void }) {
  return <div className="grid min-h-[calc(100vh-180px)] place-items-center"><div className="max-w-md text-center"><div className="relative mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-gradient-to-br from-indigo-500 to-violet-700 text-white shadow-xl shadow-indigo-600/20"><Sparkles className="h-8 w-8" /><span className="absolute -right-1 -top-1 h-5 w-5 rounded-full border-4 border-[#f6f7fb] bg-amber-400 dark:border-[#080d18]" /></div><Badge tone="violet" className="mt-6">ROADMAP</Badge><h1 className="mt-4 text-2xl font-bold text-slate-950 dark:text-white">{label}正在开发中</h1><p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">第一阶段先跑通 1688 商品采集、AI 加工、Ozon 草稿与人工审核后的 Mock 发布。这个模块已在扩展路线中预留。</p><Button className="mt-6" variant="secondary" onClick={onBack}>返回工作台<ArrowRight className="h-4 w-4" /></Button></div></div>;
}
