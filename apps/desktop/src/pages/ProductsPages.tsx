import { useCallback, useEffect, useMemo, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Bot,
  Box,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  ExternalLink,
  FileJson,
  Filter,
  Globe2,
  ImageIcon,
  Layers3,
  Link2,
  LoaderCircle,
  PackageCheck,
  PackagePlus,
  Pencil,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Trash2,
  Truck,
  WandSparkles,
  Warehouse,
} from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { demoSettings } from "../lib/demo-data";
import { formatDate, formatMoney, formatPercent, relativeTime, statusLabel } from "../lib/format";
import type { AppSettings, Product } from "../lib/types";
import { listItems, listTotal } from "../lib/types";
import { Badge, Button, Card, Dialog, EmptyState, ErrorBanner, Field, Input, LoadingState, PageHeader, Select, cn } from "../components/ui";

interface CommonProps {
  onOpenProduct: (product: Product) => void;
  onNavigate: (page: "collect" | "products" | "ai" | "drafts" | "tasks") => void;
  notify: (message: string, tone?: "success" | "error" | "info") => void;
}

function productTitle(product: Product) {
  return product.title_original || product.title || `商品 #${product.id}`;
}

function isSupportedSourceUrl(value: string) {
  try {
    const parsed = new URL(value);
    return (parsed.protocol === "https:" || parsed.protocol === "http:")
      && parsed.hostname === "detail.1688.com"
      && /^\/offer\/\d+\.html$/.test(parsed.pathname)
      && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

async function openExternalUrl(value: string) {
  if ("__TAURI_INTERNALS__" in window) {
    await openUrl(value);
    return;
  }
  window.open(value, "_blank", "noopener,noreferrer");
}

function aiTone(status?: string): "slate" | "violet" | "emerald" | "rose" {
  if (status === "completed") return "emerald";
  if (status === "processing") return "violet";
  if (status === "failed") return "rose";
  return "slate";
}

function ozonTone(status?: string): "slate" | "blue" | "amber" | "emerald" | "rose" {
  if (status === "published") return "emerald";
  if (status === "review") return "amber";
  if (status === "draft") return "blue";
  if (status === "failed") return "rose";
  return "slate";
}

function ProductImage({ product, className = "h-12 w-12" }: { product: Product; className?: string }) {
  const source = product.images?.[0];
  const [failedSource, setFailedSource] = useState<string | null>(null);
  return (
    <div className={cn("shrink-0 overflow-hidden rounded-xl bg-slate-100 ring-1 ring-slate-200/60 dark:bg-slate-800 dark:ring-slate-700", className)}>
      {source && failedSource !== source ? <img key={source} src={source} alt={productTitle(product)} className="h-full w-full object-cover" onError={() => setFailedSource(source)} /> : <div className="grid h-full place-items-center" aria-label={source ? "商品图片暂时无法加载" : "暂无商品图片"}><ImageIcon className="h-5 w-5 text-slate-400" /></div>}
    </div>
  );
}

function DataKindBadge({ product }: { product: Product }) {
  if (product.data_kind === "mock") return <Badge tone="amber">模拟样例 · 非真实商品</Badge>;
  if (product.data_kind === "real") return <Badge tone="emerald">真实采集</Badge>;
  return <Badge>数据来源待确认</Badge>;
}

export function CollectPage({ onOpenProduct, onNavigate, notify }: CommonProps) {
  const [sourceUrl, setSourceUrl] = useState("");
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState("");
  const [collected, setCollected] = useState<Product | null>(null);
  const [openingBrowser, setOpeningBrowser] = useState(false);
  const [browserMessage, setBrowserMessage] = useState("");

  useEffect(() => {
    let alive = true;
    api.sourceBrowserStatus().then((result) => { if (alive) setBrowserMessage(result.message); }).catch(() => undefined);
    return () => { alive = false; };
  }, []);

  async function openLoginBrowser() {
    const trimmed = sourceUrl.trim();
    if (trimmed && !isSupportedSourceUrl(trimmed)) {
      setError("请先输入有效的 1688 商品链接，或清空链接后打开登录浏览器。");
      return;
    }
    setOpeningBrowser(true);
    setError("");
    try {
      const result = await api.openSourceBrowser(trimmed || undefined);
      setBrowserMessage(result.message);
      notify(result.message, "info");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setOpeningBrowser(false); }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setCollected(null);
    const trimmed = sourceUrl.trim();
    if (!isSupportedSourceUrl(trimmed)) {
      setError("请输入有效的 1688 商品链接，例如 https://detail.1688.com/offer/677660197245.html");
      return;
    }
    setCollecting(true);
    setError("");
    try {
      const result = await api.collectProduct(trimmed, "real");
      if (result.product.data_kind !== "real" || result.collection_mode !== "real") {
        throw new Error("采集服务未返回真实商品数据，请更新并重启后端服务后重试。");
      }
      setCollected(result.product);
      notify("真实商品资料已采集并保存至本地商品库", "success");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setCollecting(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Product intake" title="商品采集" description="读取你提供的 1688 商品页面，保存页面可获取的商品资料。需要登录或验证时会提示处理。" actions={<Button variant="secondary" onClick={() => onNavigate("products")}><Box className="h-4 w-4" />打开商品库</Button>} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(330px,.7fr)]">
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="border-b border-slate-100 bg-gradient-to-r from-indigo-50/70 to-violet-50/30 px-6 py-5 dark:border-slate-800 dark:from-indigo-500/10 dark:to-violet-500/5">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center rounded-2xl bg-indigo-600 text-white shadow-md shadow-indigo-600/20"><Link2 className="h-5 w-5" /></div>
                <div><h2 className="font-bold text-slate-900 dark:text-white">采集 1688 商品</h2><p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">真实网页采集 · 使用独立的本地浏览器会话</p></div>
                <div className="ml-auto hidden sm:block"><Badge tone="emerald">真实采集</Badge></div>
              </div>
            </div>
            <form onSubmit={(event) => void submit(event)} className="p-6">
              <Field label="1688 商品 URL" hint="detail.1688.com/offer/商品ID.html">
                <div className="flex flex-col gap-2 sm:flex-row">
                  <div className="relative flex-1"><Globe2 className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-10" value={sourceUrl} disabled={collecting} onChange={(event) => { setSourceUrl(event.target.value); setError(""); setCollected(null); }} placeholder="https://detail.1688.com/offer/677660197245.html" autoFocus /></div>
                  <Button type="submit" disabled={collecting || openingBrowser} className="sm:min-w-32">{collecting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <PackagePlus className="h-4 w-4" />}{collecting ? "正在采集" : "开始采集"}</Button>
                </div>
              </Field>
              {error && <div className="mt-4"><ErrorBanner message={error} /></div>}
              <div className="mt-4 flex flex-col items-start gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><p className="text-xs font-semibold text-slate-700 dark:text-slate-200">1688 登录与验证</p><p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">在专用浏览器中手动完成登录或验证，再点击“开始采集”。{browserMessage && <span className="mt-1 block">{browserMessage}</span>}</p></div><Button type="button" variant="secondary" size="sm" disabled={openingBrowser || collecting} onClick={() => void openLoginBrowser()}>{openingBrowser ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}{openingBrowser ? "正在打开" : "打开 1688 登录浏览器"}</Button></div>
              <div className="mt-5 flex items-start gap-2.5 rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /><p>只有成功读取该链接的商品资料后才会保存。登录、验证或页面读取失败时会停止采集，不会以模拟商品替代。</p></div>
            </form>
          </Card>
          {collecting && <Card className="flex items-center gap-4 p-6" role="status"><LoaderCircle className="h-6 w-6 shrink-0 animate-spin text-indigo-500" /><div><h3 className="text-sm font-bold text-slate-900 dark:text-white">正在读取 1688 商品页面</h3><p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">请稍候，页面读取和资料校验完成后会显示结果。</p></div></Card>}
          {collected && (
            <Card className="overflow-hidden border-emerald-200 dark:border-emerald-500/20">
              <div className="flex items-center gap-2 border-b border-emerald-100 bg-emerald-50 px-5 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300"><CheckCircle2 className="h-4 w-4" />真实采集完成</div>
              <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center">
                <ProductImage product={collected} className="h-24 w-24" />
                <div className="min-w-0 flex-1"><h3 className="font-bold text-slate-900 dark:text-white">{productTitle(collected)}</h3><p className="mt-1 text-xs text-slate-400">商品 ID #{collected.id} · {collected.supplier || "页面未提供供应商"}</p><div className="mt-3 flex flex-wrap gap-2"><DataKindBadge product={collected} /><Badge>{formatMoney(collected.purchase_price, collected.currency)}</Badge><Badge>{collected.variants?.length || collected.sku_count || 0} SKU</Badge><Badge tone="emerald">已保存</Badge></div></div>
                <div className="flex shrink-0 flex-col gap-2"><Button onClick={() => onOpenProduct(collected)}>查看商品资料<ArrowRight className="h-4 w-4" /></Button><Button variant="ghost" onClick={() => { setSourceUrl(""); setCollected(null); }}>继续采集</Button></div>
              </div>
            </Card>
          )}
        </div>
        <div className="space-y-5">
          <Card className="p-5">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">真实采集流程</h2>
            <div className="mt-5 space-y-0">
              {[
                { icon: Globe2, title: "打开商品页面", text: "读取你输入的具体商品链接" },
                { icon: ShieldAlert, title: "检查页面状态", text: "需要登录或验证时，先完成再重试" },
                { icon: Layers3, title: "解析商品资料", text: "提取页面提供的标题、图片、SKU 等信息" },
                { icon: Warehouse, title: "保存原始资料", text: "通过校验后保存，数据来源可追溯" },
              ].map((item, index, array) => {
                const Icon = item.icon;
                return <div key={item.title} className="relative flex gap-3 pb-5 last:pb-0">{index < array.length - 1 && <span className="absolute bottom-0 left-[15px] top-8 w-px bg-slate-200 dark:bg-slate-700" />}<span className="relative grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300"><Icon className="h-4 w-4" /></span><div><p className="text-xs font-semibold text-slate-700 dark:text-slate-200">{item.title}</p><p className="mt-0.5 text-[11px] leading-5 text-slate-400">{item.text}</p></div></div>;
              })}
            </div>
          </Card>
          <Card className="p-5"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/10"><ShieldAlert className="h-4 w-4" /></span><div><h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">历史模拟数据</h3><p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">之前生成的收纳盒是固定模拟样例，与输入的商品链接无关。商品库已标记这些记录，请勿将其作为真实商品资料使用。</p></div></div></Card>
        </div>
      </div>
    </div>
  );
}

export function ProductLibraryPage({ onOpenProduct, onNavigate, notify }: CommonProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [aiStatus, setAiStatus] = useState("");
  const [ozonStatus, setOzonStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);
  const selectedHasReal = products.some((product) => product.data_kind === "real" && selected.has(String(product.id)));

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.products({ search, ai_status: aiStatus, ozon_status: ozonStatus, page, page_size: 20 });
      setProducts(listItems(result));
      setTotal(listTotal(result));
    } catch (reason) {
      setProducts([]);
      setTotal(0);
      setSelected(new Set());
      setError(`商品库读取失败，请检查本地服务连接后重试。${errorMessage(reason)}`);
    } finally { setLoading(false); }
  }, [aiStatus, ozonStatus, page, search]);

  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 250); return () => window.clearTimeout(timer); }, [load]);

  function toggleAll() {
    if (selected.size === products.length) setSelected(new Set());
    else setSelected(new Set(products.map((product) => String(product.id))));
  }

  function toggleOne(id: Product["id"]) {
    setSelected((current) => { const next = new Set(current); const key = String(id); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  }

  async function processSelected() {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    if (selectedHasReal) { notify("真实 AI 服务尚未接入，真实商品暂不能执行 AI 加工。", "info"); return; }
    setBatchProcessing(true);
    const results = await Promise.allSettled(ids.map((id) => api.processProduct(id)));
    const updated = new Map<string, Product>();
    const failed = new Set<string>();
    results.forEach((result, index) => {
      const id = ids[index];
      if (result.status === "fulfilled") updated.set(String(result.value.product.id), result.value.product);
      else failed.add(id);
    });
    setProducts((current) => current.map((product) => updated.get(String(product.id)) || product));
    setSelected(failed);
    setBatchProcessing(false);
    const completed = ids.length - failed.size;
    if (failed.size === 0) notify(`已完成 ${completed} 个商品的 AI 加工`, "success");
    else if (completed > 0) notify(`${completed} 个商品加工完成，${failed.size} 个失败，请重试`, "error");
    else notify("所选商品均未能完成 AI 加工，请查看运行日志", "error");
  }

  async function deleteProduct() {
    if (!deleteTarget) return;
    try {
      await api.deleteProduct(deleteTarget.id);
      setProducts((current) => current.filter((item) => item.id !== deleteTarget.id));
      setTotal((current) => Math.max(0, current - 1));
      notify("商品已从本地商品库删除", "success");
    } catch (reason) { notify(errorMessage(reason), "error"); }
    finally { setDeleteTarget(null); }
  }

  return (
    <div>
      <PageHeader eyebrow="Product library" title="商品库" description="管理已标准化的来源商品，跟踪 AI 加工、定价、Ozon 草稿和 Mock 发布状态。" actions={<><Button variant="secondary" onClick={() => void load()}><RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />刷新</Button><Button onClick={() => onNavigate("collect")}><PackagePlus className="h-4 w-4" />采集商品</Button></>} />
      {error && <div className="mb-4"><ErrorBanner message={error} onRetry={() => void load()} compact /></div>}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-10" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="搜索商品标题、供应商或来源 ID" /></div>
          <div className="flex flex-wrap items-center gap-2"><Filter className="h-4 w-4 text-slate-400" /><Select value={aiStatus} onChange={(event) => { setAiStatus(event.target.value); setPage(1); }}><option value="">全部 AI 状态</option><option value="pending">待处理</option><option value="processing">处理中</option><option value="completed">已完成</option><option value="failed">失败</option></Select><Select value={ozonStatus} onChange={(event) => { setOzonStatus(event.target.value); setPage(1); }}><option value="">全部 Ozon 状态</option><option value="not_created">未建草稿</option><option value="draft">草稿</option><option value="review">待审核</option><option value="published">Mock 已发布</option></Select></div>
        </div>
        {selected.size > 0 && <div className="flex items-center gap-3 border-b border-indigo-100 bg-indigo-50 px-4 py-2.5 text-xs dark:border-indigo-500/20 dark:bg-indigo-500/10"><span className="font-semibold text-indigo-700 dark:text-indigo-300">已选择 {selected.size} 个商品</span><Button variant="soft" size="sm" disabled={batchProcessing || selectedHasReal} onClick={() => void processSelected()}>{batchProcessing ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}{batchProcessing ? "正在加工" : selectedHasReal ? "真实 AI 尚未接入" : "批量模拟 AI 加工"}</Button><button className="ml-auto text-slate-500 hover:text-slate-800 dark:hover:text-white" onClick={() => setSelected(new Set())}>取消选择</button></div>}

        <div className="app-scrollbar overflow-x-auto">
          <div className="table-grid">
            <div className="table-row border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="flex items-center gap-3"><input type="checkbox" className="h-4 w-4 rounded border-slate-300 accent-indigo-600" checked={products.length > 0 && selected.size === products.length} onChange={toggleAll} aria-label="选择全部商品" />商品</div><div>采购信息</div><div>库存 / SKU</div><div>AI 状态</div><div>Ozon 状态</div><div>建议售价</div><div className="text-right">操作</div>
            </div>
            {loading && products.length === 0 ? <div className="p-5"><LoadingState label="正在加载商品库" /></div> : products.length === 0 ? <div className="p-5"><EmptyState title="没有找到商品" description="调整搜索或筛选条件，或者先从 1688 采集一个商品。" action={<Button onClick={() => onNavigate("collect")}><PackagePlus className="h-4 w-4" />采集商品</Button>} /></div> : products.map((product) => (
              <div key={product.id} className="table-row border-b border-slate-100 px-4 py-3 text-xs transition last:border-0 hover:bg-slate-50/80 dark:border-slate-800 dark:hover:bg-slate-800/30">
                <div className="flex min-w-0 items-center gap-3 pr-5"><input type="checkbox" className="h-4 w-4 shrink-0 rounded border-slate-300 accent-indigo-600" checked={selected.has(String(product.id))} onChange={() => toggleOne(product.id)} aria-label={`选择 ${productTitle(product)}`} /><ProductImage product={product} /><button className="min-w-0 text-left" onClick={() => onOpenProduct(product)}><p className="line-clamp-2 font-semibold leading-5 text-slate-800 hover:text-indigo-600 dark:text-slate-100 dark:hover:text-indigo-300">{productTitle(product)}</p><p className="mt-0.5 truncate text-[10px] text-slate-400">#{product.source_product_id || product.id} · {product.supplier || "供应商未知"}</p><div className="mt-1.5"><DataKindBadge product={product} /></div></button></div>
                <div><p className="font-semibold text-slate-700 dark:text-slate-200">{formatMoney(product.purchase_price, product.currency)}</p><p className="mt-1 text-[10px] text-slate-400">{product.source || "1688"}</p></div>
                <div><p className={cn("font-semibold", (product.stock || 0) === 0 ? "text-rose-600" : "text-slate-700 dark:text-slate-200")}>{product.stock ?? 0} 件</p><p className="mt-1 text-[10px] text-slate-400">{product.sku_count ?? product.variants?.length ?? 0} SKU</p></div>
                <div><Badge tone={aiTone(product.ai_status)}>{product.ai_status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}{statusLabel(product.ai_status)}</Badge></div>
                <div><Badge tone={ozonTone(product.ozon_status)}>{statusLabel(product.ozon_status)}</Badge></div>
                <div><p className="font-semibold text-slate-800 dark:text-slate-100">{formatMoney(product.estimated_price ?? product.suggested_price, "RUB")}</p><p className="mt-1 text-[10px] font-medium text-emerald-600">利润率 {formatPercent(product.estimated_margin ?? product.profit_margin)}</p></div>
                <div className="flex justify-end gap-1"><Button size="icon" variant="ghost" aria-label={`查看 ${productTitle(product)} 详情`} title="查看详情" onClick={() => onOpenProduct(product)}><ArrowRight className="h-4 w-4" /></Button><Button size="icon" variant="ghost" aria-label={`删除 ${productTitle(product)}`} title="删除" className="hover:text-rose-600" onClick={() => setDeleteTarget(product)}><Trash2 className="h-4 w-4" /></Button></div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500 dark:border-slate-800"><span>共 {total} 个商品 · 第 {page} 页</span><div className="flex items-center gap-1"><Button variant="ghost" size="icon" aria-label="上一页" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft className="h-4 w-4" /></Button><span className="grid h-8 min-w-8 place-items-center rounded-lg bg-indigo-50 px-2 font-semibold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">{page}</span><Button variant="ghost" size="icon" aria-label="下一页" disabled={page * 20 >= total} onClick={() => setPage((value) => value + 1)}><ChevronRight className="h-4 w-4" /></Button></div></div>
      </Card>

      <Dialog open={Boolean(deleteTarget)} title="删除这个商品？" description="商品的原始资料、AI 结果和关联草稿将从本地工作空间删除。此操作无法撤销。" onClose={() => setDeleteTarget(null)}><div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setDeleteTarget(null)}>取消</Button><Button variant="danger" onClick={() => void deleteProduct()}><Trash2 className="h-4 w-4" />确认删除</Button></div></Dialog>
    </div>
  );
}

export function ProductDetailPage({ product: initialProduct, onNavigate, notify }: { product: Product; onNavigate: CommonProps["onNavigate"]; notify: CommonProps["notify"] }) {
  const [product, setProduct] = useState(initialProduct);
  const [activeTab, setActiveTab] = useState<"source" | "ai" | "pricing">("source");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(productTitle(initialProduct));
  const [pricingSettings, setPricingSettings] = useState<AppSettings>(demoSettings);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.product(initialProduct.id).then((value) => { if (alive) { setProduct(value); setTitle(productTitle(value)); } }).catch(() => undefined).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [initialProduct.id]);

  useEffect(() => {
    let alive = true;
    api.settings().then((value) => { if (alive) setPricingSettings(value); }).catch(() => undefined);
    return () => { alive = false; };
  }, []);

  async function processAi() {
    setProcessing(true);
    try {
      const result = await api.processProduct(product.id);
      setProduct(result.product);
      notify(result.message || "AI 加工完成，Ozon 草稿已生成", "success");
    } catch (reason) { notify(errorMessage(reason), "error"); }
    finally { setProcessing(false); }
  }

  async function saveTitle() {
    const normalizedTitle = title.trim();
    if (!normalizedTitle) { notify("商品标题不能为空", "error"); return; }
    try { const updated = await api.updateProduct(product.id, { title_original: normalizedTitle }); setProduct(updated); setTitle(productTitle(updated)); setEditing(false); notify("商品标题已保存", "success"); }
    catch (reason) { notify(errorMessage(reason), "error"); }
  }

  const margin = product.estimated_margin ?? product.profit_margin ?? 0;
  return (
    <div>
      <button onClick={() => onNavigate("products")} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 transition hover:text-indigo-600 dark:text-slate-400"><ArrowLeft className="h-3.5 w-3.5" />返回商品库</button>
      <div className="mb-6 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 gap-4"><ProductImage product={product} className="h-20 w-20" /><div className="min-w-0">{editing ? <div className="flex max-w-2xl items-center gap-2"><Input aria-label="商品标题" value={title} onChange={(event) => setTitle(event.target.value)} /><Button size="sm" disabled={!title.trim()} onClick={() => void saveTitle()}>保存</Button><Button size="sm" variant="ghost" onClick={() => { setTitle(productTitle(product)); setEditing(false); }}>取消</Button></div> : <div className="flex items-start gap-2"><h1 className="max-w-3xl text-xl font-bold leading-8 text-slate-950 dark:text-white">{productTitle(product)}</h1><Button size="icon" variant="ghost" aria-label="编辑商品标题" title="编辑商品标题" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" /></Button></div>}<div className="mt-2 flex flex-wrap items-center gap-2"><Badge tone="blue">{product.source || "1688"}</Badge><DataKindBadge product={product} /><Badge tone={aiTone(product.ai_status)}>AI {statusLabel(product.ai_status)}</Badge><Badge tone={ozonTone(product.ozon_status)}>Ozon {statusLabel(product.ozon_status)}</Badge><span className="text-xs text-slate-400">更新于 {relativeTime(product.updated_at || product.created_at)}</span></div></div></div>
        <div className="flex shrink-0 flex-wrap gap-2">{product.source_url && <Button variant="secondary" onClick={() => void openExternalUrl(product.source_url!).catch((reason) => notify(errorMessage(reason), "error"))}><ExternalLink className="h-4 w-4" />来源链接</Button>}<Button disabled={processing || product.ai_status === "processing" || product.data_kind === "real"} title={product.data_kind === "real" ? "真实 AI 服务尚未接入" : undefined} onClick={() => void processAi()}>{processing ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}{product.data_kind === "real" ? "真实 AI 尚未接入" : product.ai_status === "completed" ? "重新模拟 AI 加工" : "开始模拟 AI 加工"}</Button></div>
      </div>

      {loading && <div className="mb-4"><ErrorBanner compact message="正在从本地数据库刷新商品详情…" /></div>}
      {product.data_kind === "mock" && <div className="mb-4"><ErrorBanner message="这是模拟样例，标题、图片、SKU、价格及库存均为虚构，与来源链接的实际商品无关。" /></div>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_340px]">
        <Card className="overflow-hidden">
          <div className="flex border-b border-slate-100 px-4 dark:border-slate-800">{([{ id: "source", label: "原始数据", icon: FileJson }, { id: "ai", label: "AI 加工结果", icon: Sparkles }, { id: "pricing", label: "定价与利润", icon: CircleDollarSign }] as const).map((tab) => { const Icon = tab.icon; return <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={cn("relative flex h-12 items-center gap-2 px-4 text-xs font-semibold transition", activeTab === tab.id ? "text-indigo-600 dark:text-indigo-400" : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200")}>{activeTab === tab.id && <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-indigo-600" />}<Icon className="h-4 w-4" />{tab.label}</button>; })}</div>
          <div className="p-5 sm:p-6">
            {activeTab === "source" && <SourcePanel product={product} />}
            {activeTab === "ai" && <AiPanel product={product} onProcess={() => void processAi()} processing={processing} />}
            {activeTab === "pricing" && <PricingPanel product={product} settings={pricingSettings} />}
          </div>
        </Card>
        <div className="space-y-5">
          <Card className="p-5"><h2 className="text-sm font-bold text-slate-900 dark:text-white">处理进度</h2><div className="mt-5 space-y-0">{[
            { label: "原始商品已保存", done: true, active: false },
            { label: "AI 商品理解与翻译", done: product.ai_status === "completed", active: product.ai_status === "processing" },
            { label: "Ozon 类目与属性映射", done: product.ozon_status === "draft" || product.ozon_status === "review" || product.ozon_status === "published", active: product.ai_status === "completed" && product.ozon_status === "not_created" },
            { label: "价格与利润计算", done: Boolean(product.estimated_price || product.suggested_price), active: false },
            { label: "人工审核并 Mock 发布", done: product.ozon_status === "published", active: product.ozon_status === "review" },
          ].map((step, index, array) => <div key={step.label} className="relative flex gap-3 pb-5 last:pb-0">{index < array.length - 1 && <span className={cn("absolute bottom-0 left-[9px] top-5 w-px", step.done ? "bg-emerald-300 dark:bg-emerald-700" : "bg-slate-200 dark:bg-slate-700")} />}<span className={cn("relative mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full", step.done ? "bg-emerald-500 text-white" : step.active ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-400 dark:bg-slate-800")}>{step.done ? <Check className="h-3 w-3" /> : step.active ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> : index + 1}</span><p className={cn("text-xs", step.done || step.active ? "font-semibold text-slate-700 dark:text-slate-200" : "text-slate-400")}>{step.label}</p></div>)}</div></Card>
          <Card className="p-5"><h2 className="text-sm font-bold text-slate-900 dark:text-white">商品概览</h2><dl className="mt-4 space-y-3 text-xs">{[
            ["采购价", formatMoney(product.purchase_price, product.currency)], ["建议售价", formatMoney(product.estimated_price ?? product.suggested_price, "RUB")], ["预计利润率", formatPercent(margin)], ["SKU 数量", String(product.sku_count ?? product.variants?.length ?? 0)], ["来源库存", `${product.stock ?? 0} 件`], ["采集时间", formatDate(product.created_at)],
          ].map(([label, value]) => <div key={label} className="flex items-center justify-between gap-3"><dt className="text-slate-400">{label}</dt><dd className={cn("text-right font-semibold text-slate-700 dark:text-slate-200", label === "预计利润率" && "text-emerald-600 dark:text-emerald-400")}>{value}</dd></div>)}</dl>{product.ozon_status === "review" && <Button className="mt-5 w-full" onClick={() => onNavigate("drafts")}><PackageCheck className="h-4 w-4" />前往审核草稿</Button>}</Card>
        </div>
      </div>
    </div>
  );
}

function SourcePanel({ product }: { product: Product }) {
  return <div className="space-y-6"><section><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">来源信息</h3><div className="mt-3 grid gap-3 sm:grid-cols-2"><InfoBox label="来源商品 ID" value={product.source_product_id || String(product.id)} /><InfoBox label="供应商" value={product.supplier || "—"} /><InfoBox label="原始类目" value={product.category_original || "—"} /><InfoBox label="采购价格" value={formatMoney(product.purchase_price, product.currency)} /></div></section><section><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">原始描述</h3><p className="mt-3 rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-600 dark:bg-slate-800/50 dark:text-slate-300">{product.description_original || "暂无原始描述"}</p></section><section><div className="flex items-center justify-between"><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">SKU 与库存</h3><Badge>{product.variants?.length || 0} 个规格</Badge></div>{product.variants?.length ? <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700"><div className="grid grid-cols-5 bg-slate-50 px-3 py-2 text-[10px] font-bold text-slate-400 dark:bg-slate-800"><span>内部 SKU</span><span>颜色</span><span>尺码</span><span>采购价</span><span>库存</span></div>{product.variants.map((variant, index) => <div key={variant.id || index} className="grid grid-cols-5 border-t border-slate-100 px-3 py-2.5 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300"><span className="font-mono text-[11px]">{variant.internal_sku || variant.source_sku_id || "—"}</span><span>{variant.color || "—"}</span><span>{variant.size || "—"}</span><span>{formatMoney(variant.purchase_price ?? product.purchase_price)}</span><span>{variant.stock ?? 0}</span></div>)}</div> : <p className="mt-3 text-xs text-slate-400">暂无 SKU 明细</p>}</section></div>;
}

function AiPanel({ product, onProcess, processing }: { product: Product; onProcess: () => void; processing: boolean }) {
  if (product.data_kind === "real") return <EmptyState title="真实 AI 服务尚未接入" description="真实采集的商品资料已经保存。当前 AI 仅支持模拟演示，接入真实 AI 服务后才能生成该商品的俄语资料与 Ozon 草稿。" />;
  const ai = product.ai_result;
  if (!ai) return <EmptyState title={product.ai_status === "processing" ? "AI 正在加工商品" : "还没有 AI 加工结果"} description={product.ai_status === "processing" ? "加工完成后会生成俄语标题、描述、类目和属性建议，可在任务中心查看执行记录。" : "开始 AI 加工后，原始资料仍会完整保留，结果会单独保存。"} action={product.ai_status !== "processing" ? <Button onClick={onProcess} disabled={processing}><WandSparkles className="h-4 w-4" />开始 AI 加工</Button> : undefined} />;
  return <div className="space-y-6"><div className="flex flex-wrap items-center gap-2"><Badge tone="violet">{ai.provider || "AI"}</Badge><Badge>{ai.model || "默认模型"}</Badge>{ai.duration_ms !== undefined && <span className="text-[11px] text-slate-400">耗时 {(ai.duration_ms / 1000).toFixed(1)}s</span>}</div><section><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">俄语标题</h3><p className="mt-3 rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 text-sm font-semibold leading-6 text-slate-800 dark:border-indigo-500/20 dark:bg-indigo-500/5 dark:text-slate-100">{ai.title_ru || "—"}</p></section><section><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">俄语描述</h3><p className="mt-3 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-600 dark:bg-slate-800/50 dark:text-slate-300">{ai.description_ru || "—"}</p></section><section><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">Ozon 类目建议</h3><div className="mt-3 flex items-center gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700"><span className="grid h-9 w-9 place-items-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-500/10"><Layers3 className="h-4 w-4" /></span><div><p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{ai.category_suggestion || "待映射"}</p>{ai.category_id && <p className="mt-0.5 text-[11px] text-slate-400">Category ID: {String(ai.category_id)}</p>}</div></div></section>{ai.attributes && <section><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">属性建议</h3><div className="mt-3 flex flex-wrap gap-2">{Object.entries(ai.attributes).map(([key, value]) => <span key={key} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"><span className="text-slate-400">{key}</span> · <strong className="font-semibold">{String(value)}</strong></span>)}</div></section>}{ai.risks?.length ? <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/5"><h3 className="flex items-center gap-2 text-xs font-bold text-amber-700 dark:text-amber-300"><AlertCircle className="h-4 w-4" />风险检查</h3><ul className="mt-2 space-y-1 text-xs leading-5 text-amber-800/80 dark:text-amber-200/80">{ai.risks.map((risk) => <li key={risk}>• {risk}</li>)}</ul></section> : null}</div>;
}

function PricingPanel({ product, settings }: { product: Product; settings: AppSettings }) {
  const purchase = product.purchase_price || 0;
  const domestic = Number(settings.domestic_shipping || 0);
  const international = Number(settings.international_shipping || 0);
  const exchange = Number(settings.exchange_rate || 0);
  const price = product.estimated_price ?? product.suggested_price ?? 0;
  const rubCost = (purchase + domestic + international) * exchange;
  const platformRate = Number(settings.ozon_commission_rate || 0) / 100;
  const platform = price * platformRate;
  const margin = product.estimated_margin ?? product.profit_margin ?? 0;
  const normalizedMargin = Math.abs(margin) <= 1 ? margin : margin / 100;
  const expectedProfit = Math.max(0, price * normalizedMargin);
  return <div><div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-800/50"><Truck className="h-4 w-4 text-slate-400" /><p className="mt-4 text-xl font-bold text-slate-900 dark:text-white">{formatMoney(rubCost, "RUB")}</p><p className="mt-1 text-xs text-slate-400">采购与物流折算</p></div><div className="rounded-xl bg-indigo-50 p-4 dark:bg-indigo-500/10"><CircleDollarSign className="h-4 w-4 text-indigo-500" /><p className="mt-4 text-xl font-bold text-indigo-700 dark:text-indigo-300">{formatMoney(price, "RUB")}</p><p className="mt-1 text-xs text-indigo-500">建议售价</p></div><div className="rounded-xl bg-emerald-50 p-4 dark:bg-emerald-500/10"><PackageCheck className="h-4 w-4 text-emerald-500" /><p className="mt-4 text-xl font-bold text-emerald-700 dark:text-emerald-300">{formatMoney(expectedProfit, "RUB")}</p><p className="mt-1 text-xs text-emerald-500">预计利润</p></div></div><div className="mt-6"><h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">成本明细</h3><div className="mt-3 space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">{[["1688 采购价", formatMoney(purchase)], ["国内物流", formatMoney(domestic)], ["国际物流预估", formatMoney(international)], ["汇率", `1 CNY = ${exchange} RUB`], [`Ozon 佣金（${formatPercent(settings.ozon_commission_rate)}）`, formatMoney(platform, "RUB")], ["预计利润率", formatPercent(margin)], ["规则目标利润率", formatPercent(settings.target_margin)]].map(([label, value], index) => <div key={label} className={cn("flex items-center justify-between text-xs", index === 5 && "border-t border-slate-100 pt-3 dark:border-slate-800")}><span className="text-slate-500">{label}</span><strong className="font-semibold text-slate-700 dark:text-slate-200">{value}</strong></div>)}</div></div><div className="mt-4 flex items-start gap-2 rounded-xl bg-blue-50 p-3 text-xs leading-5 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"><CircleDollarSign className="mt-0.5 h-4 w-4 shrink-0" />价格由确定性规则计算，完整结果还包含支付、广告、退货损耗与其他成本。AI 不参与数学计算。</div></div>;
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-200 px-4 py-3 dark:border-slate-700"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1.5 text-sm font-semibold text-slate-700 dark:text-slate-200">{value}</p></div>;
}

export function AiProcessingPage({ onOpenProduct, notify, onNavigate }: CommonProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.products({ page: 1, page_size: 100 });
      setProducts(listItems(result));
      setError("");
    } catch (reason) { setProducts([]); setError(`AI 队列读取失败，请检查本地服务连接后重试。${errorMessage(reason)}`); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const columns = useMemo(() => ({
    pending: products.filter((product) => !product.ai_status || product.ai_status === "pending" || product.ai_status === "failed"),
    processing: products.filter((product) => product.ai_status === "processing"),
    completed: products.filter((product) => product.ai_status === "completed"),
  }), [products]);

  async function process(product: Product) {
    if (product.data_kind === "real") { notify("真实 AI 服务尚未接入，真实商品暂不能执行 AI 加工。", "info"); return; }
    const key = String(product.id);
    setRunningIds((ids) => new Set(ids).add(key));
    try { const result = await api.processProduct(product.id); setProducts((items) => items.map((item) => item.id === product.id ? result.product : item)); notify(result.message || `商品 #${product.id} 已完成 AI 加工`, "success"); }
    catch (reason) { notify(errorMessage(reason), "error"); }
    finally { setRunningIds((ids) => { const next = new Set(ids); next.delete(key); return next; }); }
  }

  return <div><PageHeader eyebrow="AI workspace" title="AI 商品加工" description="真实 AI 服务尚未接入；历史模拟样例可以演示俄语资料与 Ozon 草稿生成。原始商品数据独立保存。" actions={<><Button variant="secondary" onClick={() => void load()}><RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />刷新</Button><Button disabled={!columns.pending.some((product) => product.data_kind !== "real")} onClick={() => columns.pending.filter((product) => product.data_kind !== "real").slice(0, 5).forEach((product) => void process(product))}><Sparkles className="h-4 w-4" />批量模拟加工</Button></>} />{error && <div className="mb-4"><ErrorBanner compact message={error} onRetry={() => void load()} /></div>}{loading && products.length === 0 ? <LoadingState label="正在读取 AI 加工队列" /> : <div className="grid gap-5 lg:grid-cols-3">{[
    { key: "pending" as const, title: "待处理", description: "等待生成俄语资料", icon: Clock3, tone: "amber" }, { key: "processing" as const, title: "处理中", description: "流程任务正在执行", icon: LoaderCircle, tone: "violet" }, { key: "completed" as const, title: "已完成", description: "已生成可审核草稿", icon: CheckCircle2, tone: "emerald" },
  ].map((column) => { const Icon = column.icon; const items = columns[column.key]; return <Card key={column.key} className="overflow-hidden"><div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5 dark:border-slate-800"><div className="flex items-center gap-2.5"><span className={cn("grid h-8 w-8 place-items-center rounded-lg", column.tone === "amber" ? "bg-amber-50 text-amber-600 dark:bg-amber-500/10" : column.tone === "violet" ? "bg-violet-50 text-violet-600 dark:bg-violet-500/10" : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10")}><Icon className={cn("h-4 w-4", column.key === "processing" && "animate-spin")} /></span><div><h2 className="text-sm font-bold text-slate-800 dark:text-slate-100">{column.title}</h2><p className="text-[10px] text-slate-400">{column.description}</p></div></div><Badge>{items.length}</Badge></div><div className="app-scrollbar max-h-[620px] space-y-2 overflow-y-auto p-3">{items.length === 0 ? <div className="py-16 text-center text-xs text-slate-400">暂无商品</div> : items.map((product) => <div key={product.id} className="rounded-xl border border-slate-100 p-3 transition hover:border-indigo-200 dark:border-slate-800 dark:hover:border-indigo-500/30"><div className="flex gap-3"><ProductImage product={product} /><button className="min-w-0 flex-1 text-left" onClick={() => onOpenProduct(product)}><p className="line-clamp-2 text-xs font-semibold leading-5 text-slate-700 hover:text-indigo-600 dark:text-slate-200">{productTitle(product)}</p><p className="mt-1 text-[10px] text-slate-400">#{product.id} · {relativeTime(product.updated_at || product.created_at)}</p><div className="mt-1.5"><DataKindBadge product={product} /></div></button></div>{column.key === "pending" && <Button className="mt-3 w-full" size="sm" variant="soft" disabled={runningIds.has(String(product.id)) || product.data_kind === "real"} onClick={() => void process(product)}>{runningIds.has(String(product.id)) ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : product.ai_status === "failed" ? <RefreshCw className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}{product.data_kind === "real" ? "真实 AI 尚未接入" : product.ai_status === "failed" ? "重新模拟加工" : "开始模拟加工"}</Button>}{column.key === "processing" && <div className="mt-3"><div className="mb-1.5 text-[10px] text-slate-400">正在生成结构化结果 · 进度以任务中心为准</div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full w-2/3 animate-pulse rounded-full bg-gradient-to-r from-violet-500 to-indigo-500" /></div></div>}{column.key === "completed" && <div className="mt-3 flex items-center justify-between"><span className="text-[10px] font-medium text-emerald-600">俄语资料已生成</span><Button size="sm" variant="ghost" onClick={() => onOpenProduct(product)}>查看结果<ArrowRight className="h-3.5 w-3.5" /></Button></div>}</div>)}</div></Card>; })}</div>}<Card className="mt-5 flex flex-col gap-4 p-5 sm:flex-row sm:items-center"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10"><Bot className="h-5 w-5" /></span><div className="flex-1"><h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">所有 AI 操作都可追踪</h3><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">系统保存 Provider、模型、结构化输入输出、耗时和错误；API Key 永远不会写入日志。</p></div><Button variant="secondary" onClick={() => onNavigate("tasks")}>查看任务中心<ArrowRight className="h-4 w-4" /></Button></Card></div>;
}
