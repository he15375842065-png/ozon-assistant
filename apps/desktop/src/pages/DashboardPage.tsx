import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Box,
  CheckCircle2,
  CircleDotDashed,
  Clock3,
  PackagePlus,
  Play,
  Rocket,
  ScanSearch,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { demoDashboard } from "../lib/demo-data";
import { formatMoney, formatPercent, relativeTime, statusLabel } from "../lib/format";
import type { DashboardData, Product } from "../lib/types";
import type { PageId } from "../components/AppShell";
import { Badge, Button, Card, ErrorBanner, PageHeader, Skeleton, cn } from "../components/ui";

interface Props {
  onNavigate: (page: PageId, label?: string) => void;
  onOpenProduct: (product: Product) => void;
}

const statCards = [
  { key: "product_total" as const, label: "商品总数", helper: "本地商品库", icon: Box, tone: "indigo" },
  { key: "pending_ai" as const, label: "待 AI 加工", helper: "等待生成俄语资料", icon: Sparkles, tone: "violet" },
  { key: "pending_review" as const, label: "待人工审核", helper: "Mock 发布前检查", icon: Clock3, tone: "amber" },
  { key: "published" as const, label: "Mock 已发布", helper: "本地模拟结果", icon: CheckCircle2, tone: "emerald" },
];

const toneClasses: Record<string, { icon: string; tint: string }> = {
  indigo: { icon: "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300", tint: "text-indigo-600 dark:text-indigo-400" },
  violet: { icon: "bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-300", tint: "text-violet-600 dark:text-violet-400" },
  amber: { icon: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300", tint: "text-amber-600 dark:text-amber-400" },
  emerald: { icon: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300", tint: "text-emerald-600 dark:text-emerald-400" },
};

export function DashboardPage({ onNavigate, onOpenProduct }: Props) {
  const [data, setData] = useState<DashboardData>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.dashboard());
    } catch (reason) {
      setData(demoDashboard);
      setError(`本地服务暂未连接，当前显示预览数据。${errorMessage(reason)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const recentProducts = data?.recent_products || [];
  const recentErrors = data?.recent_errors || [];
  const runningTasks = data?.task_counts?.running || 0;
  const pendingTasks = data?.task_counts?.pending || 0;
  const successfulTasks = data?.task_counts?.success || 0;
  const failedTasks = data?.task_counts?.failed || 0;
  const measuredTasks = successfulTasks + failedTasks;
  const successRate = measuredTasks > 0 ? formatPercent(successfulTasks / measuredTasks, 0) : "—";

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="早上好，开始今天的 Ozon 运营"
        description="从 1688 采集到 Ozon 草稿与 Mock 发布，关键进度和待办都集中在这里。"
        actions={<Button onClick={() => onNavigate("collect")}><PackagePlus className="h-4 w-4" />采集新商品</Button>}
      />

      {error && <div className="mb-5"><ErrorBanner message={error} onRetry={() => void load()} compact /></div>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          const colors = toneClasses[stat.tone];
          return (
            <Card key={stat.key} className="group relative overflow-hidden p-5 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/40 dark:hover:shadow-black/20">
              <div className="flex items-start">
                <div className={cn("grid h-10 w-10 place-items-center rounded-xl", colors.icon)}><Icon className="h-[19px] w-[19px]" /></div>
              </div>
              {loading ? <Skeleton className="mt-5 h-9 w-20" /> : <p className="mt-5 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">{data?.[stat.key] ?? 0}</p>}
              <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">{stat.label}</p>
              <p className="mt-0.5 text-xs text-slate-400">{stat.helper}</p>
            </Card>
          );
        })}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,.85fr)]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">最近采集</h2>
              <p className="mt-0.5 text-xs text-slate-400">最新进入商品库的 1688 商品</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onNavigate("products")}>查看全部<ArrowRight className="h-3.5 w-3.5" /></Button>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {loading ? Array.from({ length: 3 }).map((_, index) => <div key={index} className="flex items-center gap-3 px-5 py-4"><Skeleton className="h-12 w-12" /><div className="flex-1"><Skeleton className="h-3.5 w-3/5" /><Skeleton className="mt-2 h-3 w-2/5" /></div></div>) : recentProducts.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-slate-400">还没有采集商品</div>
            ) : recentProducts.map((product) => (
              <button key={product.id} className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800/50" onClick={() => onOpenProduct(product)}>
                <div className="h-12 w-12 shrink-0 overflow-hidden rounded-xl bg-slate-100 dark:bg-slate-800">
                  {product.images?.[0] ? <img src={product.images[0]} alt="" className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center"><Box className="h-4 w-4 text-slate-400" /></div>}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">{product.title_original || product.title || `商品 #${product.id}`}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
                    <span>1688</span><span>{formatMoney(product.purchase_price, product.currency)}</span><span>{product.sku_count ?? product.variants?.length ?? 0} SKU</span><span>{relativeTime(product.created_at)}</span>
                  </div>
                </div>
                <Badge tone={product.ai_status === "completed" ? "emerald" : product.ai_status === "failed" ? "rose" : product.ai_status === "processing" ? "violet" : "slate"}>{statusLabel(product.ai_status)}</Badge>
                <ArrowRight className="h-4 w-4 shrink-0 text-slate-300" />
              </button>
            ))}
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="relative overflow-hidden bg-gradient-to-br from-indigo-600 via-indigo-600 to-violet-700 p-5 text-white dark:border-indigo-500/30">
            <div className="absolute -right-14 -top-14 h-40 w-40 rounded-full bg-white/10" /><div className="absolute -bottom-20 right-16 h-36 w-36 rounded-full bg-violet-300/10" />
            <div className="relative flex items-start justify-between">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/15"><Rocket className="h-5 w-5" /></span>
              <Badge className="bg-white/15 text-white ring-white/20">纵向链路</Badge>
            </div>
            <h2 className="relative mt-5 text-lg font-bold">一条链路，完成 Mock 发布演示</h2>
            <p className="relative mt-1 text-xs leading-5 text-indigo-100">采集商品后，AI 会准备俄语资料、类目属性和定价草稿，最终由你确认模拟发布；不会写入真实 Ozon 店铺。</p>
            <div className="relative mt-5 flex items-center gap-1.5 text-[10px] font-semibold text-indigo-100">
              {["1688", "AI", "定价", "审核", "Ozon"].map((step, index) => <span key={step} className="contents"><span className="rounded-md bg-white/10 px-2 py-1">{step}</span>{index < 4 && <ArrowRight className="h-3 w-3 opacity-60" />}</span>)}
            </div>
            <Button className="relative mt-5 bg-white text-indigo-700 hover:bg-indigo-50" size="sm" onClick={() => onNavigate("collect")}><Play className="h-3.5 w-3.5" />开始采集</Button>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">任务状态</h2>
                <p className="mt-0.5 text-xs text-slate-400">本地任务管理器</p>
              </div>
              <Button variant="ghost" size="icon" aria-label="打开任务中心" title="打开任务中心" onClick={() => onNavigate("tasks")}><ArrowRight className="h-4 w-4" /></Button>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2">
              <div className="rounded-xl bg-indigo-50 p-3 dark:bg-indigo-500/10"><CircleDotDashed className="h-4 w-4 text-indigo-500" /><p className="mt-3 text-xl font-bold text-slate-900 dark:text-white">{runningTasks}</p><p className="text-[10px] text-slate-500">运行中</p></div>
              <div className="rounded-xl bg-amber-50 p-3 dark:bg-amber-500/10"><Clock3 className="h-4 w-4 text-amber-500" /><p className="mt-3 text-xl font-bold text-slate-900 dark:text-white">{pendingTasks}</p><p className="text-[10px] text-slate-500">等待中</p></div>
              <div className="rounded-xl bg-emerald-50 p-3 dark:bg-emerald-500/10"><TrendingUp className="h-4 w-4 text-emerald-500" /><p className="mt-3 text-xl font-bold text-slate-900 dark:text-white">{successRate}</p><p className="text-[10px] text-slate-500">成功率</p></div>
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div><h2 className="text-sm font-bold text-slate-900 dark:text-white">待办建议</h2><p className="mt-0.5 text-xs text-slate-400">根据当前商品状态生成</p></div>
            <ScanSearch className="h-5 w-5 text-indigo-500" />
          </div>
          <div className="mt-4 space-y-2">
            <button onClick={() => onNavigate("ai")} className="flex w-full items-center gap-3 rounded-xl border border-slate-100 p-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/40 dark:border-slate-800 dark:hover:border-indigo-500/30 dark:hover:bg-indigo-500/5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-violet-50 text-violet-600 dark:bg-violet-500/10"><Bot className="h-4 w-4" /></span><div className="flex-1"><p className="text-xs font-semibold text-slate-800 dark:text-slate-100">批量处理待 AI 商品</p><p className="mt-0.5 text-[11px] text-slate-400">还有 {data?.pending_ai ?? 0} 个商品等待加工</p></div><ArrowRight className="h-4 w-4 text-slate-300" />
            </button>
            <button onClick={() => onNavigate("drafts")} className="flex w-full items-center gap-3 rounded-xl border border-slate-100 p-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/40 dark:border-slate-800 dark:hover:border-indigo-500/30 dark:hover:bg-indigo-500/5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-500/10"><CheckCircle2 className="h-4 w-4" /></span><div className="flex-1"><p className="text-xs font-semibold text-slate-800 dark:text-slate-100">审核 Ozon 商品草稿</p><p className="mt-0.5 text-[11px] text-slate-400">Mock 发布前请确认标题、类目、属性与价格</p></div><ArrowRight className="h-4 w-4 text-slate-300" />
            </button>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div><h2 className="text-sm font-bold text-slate-900 dark:text-white">最近异常</h2><p className="mt-0.5 text-xs text-slate-400">需要关注的运行记录</p></div>
            <Button variant="ghost" size="sm" onClick={() => onNavigate("logs")}>查看日志<ArrowRight className="h-3.5 w-3.5" /></Button>
          </div>
          <div className="mt-4 space-y-2">
            {recentErrors.length ? recentErrors.slice(0, 3).map((log) => (
              <div key={log.id} className="flex items-start gap-3 rounded-xl bg-rose-50/70 p-3 dark:bg-rose-500/5"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" /><div className="min-w-0 flex-1"><p className="line-clamp-2 text-xs font-medium leading-5 text-slate-700 dark:text-slate-200">{log.message}</p><p className="mt-1 text-[10px] text-slate-400">{log.module || "系统"} · {relativeTime(log.created_at)}</p></div></div>
            )) : <div className="flex min-h-24 items-center justify-center gap-2 text-xs text-slate-400"><CheckCircle2 className="h-4 w-4 text-emerald-500" />当前没有需要处理的异常</div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
