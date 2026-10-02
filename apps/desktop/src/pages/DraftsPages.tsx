import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  BadgeCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Eye,
  ImageIcon,
  Layers3,
  LoaderCircle,
  PencilLine,
  Plus,
  RefreshCw,
  Save,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Tags,
  Trash2,
} from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { demoDrafts } from "../lib/demo-data";
import { formatDate, formatMoney, formatPercent, statusLabel } from "../lib/format";
import type { Draft, DraftSku } from "../lib/types";
import { listItems } from "../lib/types";
import { Badge, Button, Card, Dialog, EmptyState, ErrorBanner, Field, Input, LoadingState, PageHeader, Select, Textarea, cn } from "../components/ui";

interface DraftListProps {
  onOpenDraft: (draft: Draft) => void;
  onNavigateProducts: () => void;
}

function draftTitle(draft: Draft) { return draft.title_ru || draft.title || `Ozon 草稿 #${draft.id}`; }

function draftTone(status?: string): "slate" | "blue" | "amber" | "emerald" | "rose" {
  if (status === "published") return "emerald";
  if (status === "review") return "amber";
  if (status === "draft") return "blue";
  if (status === "failed") return "rose";
  return "slate";
}

export function DraftsPage({ onOpenDraft, onNavigateProducts }: DraftListProps) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.drafts(status);
      setDrafts(listItems(result));
      setError("");
    } catch (reason) {
      setDrafts(demoDrafts.filter((draft) => !status || draft.status === status));
      setError(`本地服务暂未连接，当前显示预览数据。${errorMessage(reason)}`);
    } finally { setLoading(false); }
  }, [status]);

  useEffect(() => { void load(); }, [load]);

  const visibleDrafts = useMemo(() => drafts.filter((draft) => !search || draftTitle(draft).toLowerCase().includes(search.toLowerCase()) || String(draft.id).includes(search)), [drafts, search]);

  return (
    <div>
      <PageHeader eyebrow="Ozon publishing" title="Ozon 草稿" description="AI 建议已转换为可编辑草稿。请人工确认资料后执行 Mock 发布；当前不会写入真实 Ozon 店铺。" actions={<Button variant="secondary" onClick={() => void load()}><RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />刷新草稿</Button>} />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        {[{ label: "待审核", value: drafts.filter((item) => item.status === "review").length, icon: ClipboardCheck, tone: "amber" }, { label: "编辑中", value: drafts.filter((item) => item.status === "draft").length, icon: PencilLine, tone: "blue" }, { label: "Mock 已发布", value: drafts.filter((item) => item.status === "published").length, icon: BadgeCheck, tone: "emerald" }].map((item) => { const Icon = item.icon; return <Card key={item.label} className="flex items-center gap-4 p-4"><span className={cn("grid h-10 w-10 place-items-center rounded-xl", item.tone === "amber" ? "bg-amber-50 text-amber-600 dark:bg-amber-500/10" : item.tone === "blue" ? "bg-blue-50 text-blue-600 dark:bg-blue-500/10" : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10")}><Icon className="h-[18px] w-[18px]" /></span><div><p className="text-xl font-bold text-slate-950 dark:text-white">{item.value}</p><p className="text-xs text-slate-400">{item.label}</p></div></Card>; })}
      </div>
      {error && <div className="mb-4"><ErrorBanner compact message={error} onRetry={() => void load()} /></div>}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center"><div className="relative flex-1"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-10" placeholder="搜索俄语标题或草稿 ID" value={search} onChange={(event) => setSearch(event.target.value)} /></div><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">全部状态</option><option value="review">待审核</option><option value="draft">编辑中</option><option value="published">Mock 已发布</option><option value="failed">发布失败</option></Select></div>
        <div className="app-scrollbar overflow-x-auto"><div className="min-w-[880px]"><div className="table-row-drafts border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:border-slate-800 dark:bg-slate-950/40"><div>草稿商品</div><div>Ozon 类目</div><div>建议售价</div><div>预计利润</div><div>状态 / 更新</div><div className="text-right">操作</div></div>
          {loading && drafts.length === 0 ? <div className="p-5"><LoadingState label="正在加载 Ozon 草稿" /></div> : visibleDrafts.length === 0 ? <div className="p-5"><EmptyState title="没有找到草稿" description="完成 AI 商品加工后，系统会生成可审核的 Ozon 草稿。" action={<Button variant="secondary" onClick={onNavigateProducts}>返回商品库</Button>} /></div> : visibleDrafts.map((draft) => <div key={draft.id} className="table-row-drafts border-b border-slate-100 px-4 py-3 text-xs last:border-0 hover:bg-slate-50/80 dark:border-slate-800 dark:hover:bg-slate-800/30"><div className="flex min-w-0 items-center gap-3 pr-5"><div className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100 dark:bg-slate-800">{draft.images?.[0] ? <img src={draft.images[0]} alt="" className="h-full w-full object-cover" /> : <ImageIcon className="h-4 w-4 text-slate-400" />}</div><button className="min-w-0 text-left" onClick={() => onOpenDraft(draft)}><p className="line-clamp-2 font-semibold leading-5 text-slate-800 hover:text-indigo-600 dark:text-slate-100">{draftTitle(draft)}</p><p className="mt-0.5 text-[10px] text-slate-400">草稿 #{draft.id} · 商品 #{draft.product_id || "—"}</p></button></div><div><p className="line-clamp-2 pr-4 text-slate-600 dark:text-slate-300">{draft.category_name || "待选择类目"}</p>{draft.category_id && <p className="mt-1 text-[10px] text-slate-400">ID {String(draft.category_id)}</p>}</div><div className="font-semibold text-slate-800 dark:text-slate-100">{formatMoney(draft.suggested_price ?? draft.price, "RUB")}</div><div><span className="font-semibold text-emerald-600">{formatPercent(draft.profit_margin)}</span></div><div><Badge tone={draftTone(draft.status)}>{statusLabel(draft.status)}</Badge><p className="mt-1.5 text-[10px] text-slate-400">{formatDate(draft.updated_at)}</p></div><div className="flex justify-end"><Button size="sm" variant={draft.status === "review" ? "soft" : "ghost"} onClick={() => onOpenDraft(draft)}>{draft.status === "review" ? <ClipboardCheck className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}{draft.status === "review" ? "审核" : "查看"}</Button></div></div>)}</div></div>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500 dark:border-slate-800"><span>共 {visibleDrafts.length} 个草稿</span><div className="flex gap-1"><Button size="icon" variant="ghost" disabled><ChevronLeft className="h-4 w-4" /></Button><span className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-50 font-semibold text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">1</span><Button size="icon" variant="ghost" disabled><ChevronRight className="h-4 w-4" /></Button></div></div>
      </Card>
    </div>
  );
}

interface ReviewProps {
  draft: Draft;
  onBack: () => void;
  notify: (message: string, tone?: "success" | "error" | "info") => void;
  onPublished: () => void;
}

interface EditableAttribute {
  id: string;
  key: string;
  value: string;
}

function editableAttributes(attributes?: Record<string, unknown>): EditableAttribute[] {
  return Object.entries(attributes || {}).map(([key, value], index) => ({
    id: `attribute-${index}-${key}`,
    key,
    value: String(value ?? ""),
  }));
}

function attributePayload(rows: EditableAttribute[]): Record<string, string> {
  return Object.fromEntries(
    rows
      .map((row) => [row.key.trim(), row.value.trim()] as const)
      .filter(([key]) => Boolean(key)),
  );
}

export function DraftReviewPage({ draft: initialDraft, onBack, notify, onPublished }: ReviewProps) {
  const [draft, setDraft] = useState(initialDraft);
  const [title, setTitle] = useState(draftTitle(initialDraft));
  const [description, setDescription] = useState(initialDraft.description_ru || initialDraft.description || "");
  const [categoryId, setCategoryId] = useState(String(initialDraft.category_id || ""));
  const [categoryName, setCategoryName] = useState(initialDraft.category_name || "");
  const [price, setPrice] = useState(String(initialDraft.suggested_price ?? initialDraft.price ?? ""));
  const [weightG, setWeightG] = useState(String(initialDraft.weight_g ?? ""));
  const [lengthMm, setLengthMm] = useState(String(initialDraft.length_mm ?? ""));
  const [widthMm, setWidthMm] = useState(String(initialDraft.width_mm ?? ""));
  const [heightMm, setHeightMm] = useState(String(initialDraft.height_mm ?? ""));
  const [attributes, setAttributes] = useState<EditableAttribute[]>(() => editableAttributes(initialDraft.attributes));
  const [skus, setSkus] = useState<DraftSku[]>(() => (initialDraft.skus || []).map((sku) => ({ ...sku })));
  const [images, setImages] = useState<string[]>(() => [...(initialDraft.images || [])]);
  const [imageUrl, setImageUrl] = useState("");
  const [imageError, setImageError] = useState("");
  const [activeSection, setActiveSection] = useState<"content" | "category" | "sku" | "images">("content");
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api.draft(initialDraft.id).then((value) => {
      if (!alive) return;
      setDraft(value);
      setTitle(draftTitle(value));
      setDescription(value.description_ru || value.description || "");
      setCategoryId(String(value.category_id || ""));
      setCategoryName(value.category_name || "");
      setPrice(String(value.suggested_price ?? value.price ?? ""));
      setWeightG(String(value.weight_g ?? ""));
      setLengthMm(String(value.length_mm ?? ""));
      setWidthMm(String(value.width_mm ?? ""));
      setHeightMm(String(value.height_mm ?? ""));
      setAttributes(editableAttributes(value.attributes));
      setSkus((value.skus || []).map((sku) => ({ ...sku })));
      setImages([...(value.images || [])]);
    }).catch(() => undefined);
    return () => { alive = false; };
  }, [initialDraft.id]);

  const locked = draft.status === "published" || draft.status === "stale";
  const patch = useMemo<Partial<Draft>>(() => {
    const data: Partial<Draft> = {
      title_ru: title.trim(),
      description_ru: description.trim(),
      category_id: categoryId.trim(),
      attributes: attributePayload(attributes),
      images,
      skus: skus.map((sku) => ({ ...sku, price: Number(price) || 0, stock: Math.max(0, Number(sku.stock) || 0) })),
      suggested_price: Number(price) || 0,
      stock: skus.reduce((total, sku) => total + Math.max(0, Number(sku.stock) || 0), 0),
    };
    // Weight/dimensions are required by the real Ozon import; omit when empty.
    const weight = Number(weightG);
    if (weight > 0) data.weight_g = Math.round(weight);
    const length = Number(lengthMm);
    if (length > 0) data.length_mm = Math.round(length);
    const width = Number(widthMm);
    if (width > 0) data.width_mm = Math.round(width);
    const height = Number(heightMm);
    if (height > 0) data.height_mm = Math.round(height);
    return data;
  }, [attributes, categoryId, description, heightMm, images, lengthMm, price, skus, title, weightG, widthMm]);

  function syncDraftState(value: Draft) {
    setDraft(value);
    setTitle(draftTitle(value));
    setDescription(value.description_ru || value.description || "");
    setCategoryId(String(value.category_id || ""));
    setCategoryName(value.category_name || "");
    setPrice(String(value.suggested_price ?? value.price ?? ""));
    setWeightG(String(value.weight_g ?? ""));
    setLengthMm(String(value.length_mm ?? ""));
    setWidthMm(String(value.width_mm ?? ""));
    setHeightMm(String(value.height_mm ?? ""));
    setAttributes(editableAttributes(value.attributes));
    setSkus((value.skus || []).map((sku) => ({ ...sku })));
    setImages([...(value.images || [])]);
  }

  async function save() {
    setSaving(true); setError("");
    try { const updated = await api.updateDraft(draft.id, patch); syncDraftState(updated); notify("草稿修改已保存", "success"); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setSaving(false); }
  }

  async function publish() {
    if (!acknowledged) return;
    setPublishing(true); setError("");
    try {
      await api.updateDraft(draft.id, patch);
      const result = await api.publishDraft(draft.id);
      syncDraftState(result.draft);
      setConfirmOpen(false);
      notify("Mock 发布成功，草稿状态已更新", "success");
      onPublished();
    } catch (reason) { setError(errorMessage(reason)); setConfirmOpen(false); }
    finally { setPublishing(false); setAcknowledged(false); }
  }

  function addAttribute() {
    setAttributes((current) => [...current, { id: `attribute-${Date.now()}`, key: "", value: "" }]);
  }

  function updateAttribute(id: string, field: "key" | "value", value: string) {
    setAttributes((current) => current.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }

  function updateSku(index: number, field: "price" | "stock", value: string) {
    if (field === "price") {
      setPrice(value);
      setSkus((current) => current.map((sku) => ({ ...sku, price: Number(value) || 0 })));
      return;
    }
    setSkus((current) => current.map((sku, skuIndex) => skuIndex === index ? { ...sku, stock: Math.max(0, Number(value) || 0) } : sku));
  }

  function addImage() {
    const candidate = imageUrl.trim();
    try {
      const parsed = new URL(candidate);
      if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error("invalid protocol");
      if (images.includes(candidate)) {
        setImageError("该图片已在列表中");
        return;
      }
      setImages((current) => [...current, candidate]);
      setImageUrl("");
      setImageError("");
    } catch {
      setImageError("请输入有效的 http 或 https 图片地址");
    }
  }

  function moveImage(index: number, offset: number) {
    setImages((current) => {
      const nextIndex = index + offset;
      if (nextIndex < 0 || nextIndex >= current.length) return current;
      const next = [...current];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  }

  const reviewChecks: Array<[string, boolean]> = [
    ["俄语标题", Boolean(title.trim())],
    ["商品描述", Boolean(description.trim())],
    ["Ozon 类目", Boolean(categoryId.trim())],
    ["商品属性", Object.keys(attributePayload(attributes)).length > 0],
    ["SKU 与库存", skus.length > 0],
    ["商品价格", Number(price) > 0],
    ["商品图片", images.length > 0],
  ];
  const completeness = reviewChecks.filter(([, ready]) => ready).length;
  const percent = Math.round((completeness / reviewChecks.length) * 100);

  return (
    <div>
      <button onClick={onBack} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 transition hover:text-indigo-600 dark:text-slate-400">
        <ArrowLeft className="h-3.5 w-3.5" />返回草稿列表
      </button>
      <PageHeader
        eyebrow={`Draft #${draft.id}`}
        title="审核 Ozon 商品草稿"
        description="逐项核对 AI 建议与价格。当前只调用 Mock Connector，确认后仅记录本地模拟发布结果。"
        actions={<>
          <Button variant="secondary" disabled={saving || locked} onClick={() => void save()}>
            {saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存草稿
          </Button>
          <Button disabled={publishing || locked || percent < 100} onClick={() => setConfirmOpen(true)}>
            <Send className="h-4 w-4" />{draft.status === "published" ? "Mock 已发布" : draft.status === "stale" ? "草稿已失效" : "确认 Mock 发布"}
          </Button>
        </>}
      />
      {locked && <div className="mb-4"><ErrorBanner message={draft.status === "published" ? "该草稿已完成本地 Mock 发布，未发送到真实 Ozon 店铺；当前为只读状态。" : "源商品已变化，该草稿已失效，请重新进行 AI 加工。"} /></div>}
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_350px]">
        <Card className="overflow-hidden">
          <div className="app-scrollbar flex overflow-x-auto border-b border-slate-100 px-3 dark:border-slate-800">
            {([
              { id: "content", label: "内容", icon: Sparkles },
              { id: "category", label: "类目与属性", icon: Layers3 },
              { id: "sku", label: "SKU 与库存", icon: Tags },
              { id: "images", label: "商品图片", icon: ImageIcon },
            ] as const).map((section) => {
              const Icon = section.icon;
              return <button key={section.id} onClick={() => setActiveSection(section.id)} className={cn("relative flex h-12 shrink-0 items-center gap-2 px-4 text-xs font-semibold transition", activeSection === section.id ? "text-indigo-600 dark:text-indigo-400" : "text-slate-500 dark:text-slate-400")}>
                {activeSection === section.id && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-indigo-600" />}
                <Icon className="h-4 w-4" />{section.label}
              </button>;
            })}
          </div>

          <div className="p-5 sm:p-6">
            {activeSection === "content" && <div className="space-y-5">
              <div className="flex items-start gap-3 rounded-xl border border-violet-100 bg-violet-50/70 p-4 dark:border-violet-500/20 dark:bg-violet-500/5">
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" />
                <div><p className="text-xs font-semibold text-violet-700 dark:text-violet-300">以下内容由 AI 生成，发布前请人工确认</p><p className="mt-1 text-[11px] leading-5 text-violet-600/80 dark:text-violet-300/70">可以直接编辑俄语标题和描述，保存后不会修改 1688 原始资料。</p></div>
              </div>
              <Field label="俄语商品标题" hint={`${title.length} / 200`}><Input disabled={locked} value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} /></Field>
              <Field label="俄语商品描述" hint="支持纯文本"><Textarea disabled={locked} rows={11} value={description} onChange={(event) => setDescription(event.target.value)} /></Field>
            </div>}

            {activeSection === "category" && <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Ozon Category ID"><Input disabled={locked} value={categoryId} onChange={(event) => setCategoryId(event.target.value)} placeholder="输入类目 ID" /></Field>
                <Field label="AI 建议类目" hint="随 AI 结果保留"><Input readOnly value={categoryName} placeholder="暂无建议类目" className="bg-slate-50 text-slate-500 dark:bg-slate-800/70" /></Field>
              </div>
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">商品属性</h3>
                  <Button size="sm" variant="secondary" disabled={locked} onClick={addAttribute}><Plus className="h-3.5 w-3.5" />添加属性</Button>
                </div>
                <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
                  {attributes.length ? attributes.map((attribute) => <div key={attribute.id} className="grid grid-cols-[minmax(110px,0.8fr)_minmax(160px,1.4fr)_42px] items-center gap-3 border-b border-slate-100 px-3 py-2.5 last:border-0 dark:border-slate-800">
                    <Input aria-label="属性名" disabled={locked} className="h-8" value={attribute.key} onChange={(event) => updateAttribute(attribute.id, "key", event.target.value)} placeholder="属性名" />
                    <Input aria-label="属性值" disabled={locked} className="h-8" value={attribute.value} onChange={(event) => updateAttribute(attribute.id, "value", event.target.value)} placeholder="属性值" />
                    <Button aria-label="删除属性" title="删除属性" disabled={locked} size="icon" variant="ghost" onClick={() => setAttributes((current) => current.filter((row) => row.id !== attribute.id))}><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>) : <div className="p-10 text-center text-xs text-slate-400">暂无属性，请添加 Ozon 所需属性</div>}
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">重量与尺寸</h3>
                  <span className="text-[10px] text-slate-400">真实发布必填</span>
                </div>
                <div className="mt-3 grid gap-4 sm:grid-cols-4">
                  <Field label="重量" hint="克"><Input disabled={locked} type="number" min="1" step="1" value={weightG} onChange={(event) => setWeightG(event.target.value)} placeholder="例如 300" /></Field>
                  <Field label="长" hint="毫米"><Input disabled={locked} type="number" min="1" step="1" value={lengthMm} onChange={(event) => setLengthMm(event.target.value)} placeholder="例如 200" /></Field>
                  <Field label="宽" hint="毫米"><Input disabled={locked} type="number" min="1" step="1" value={widthMm} onChange={(event) => setWidthMm(event.target.value)} placeholder="例如 150" /></Field>
                  <Field label="高" hint="毫米"><Input disabled={locked} type="number" min="1" step="1" value={heightMm} onChange={(event) => setHeightMm(event.target.value)} placeholder="例如 50" /></Field>
                </div>
              </div>
              <div className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />AI 类目与属性只是建议，请按 Ozon 后台的最新要求核对必填项。</div>
            </div>}

            {activeSection === "sku" && <div>
              <div className="mb-4 flex items-center justify-between"><div><h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">销售规格</h3><p className="mt-0.5 text-xs text-slate-400">Ozon 草稿采用统一售价，可分别修改每个 SKU 的库存</p></div><Badge>{skus.length} SKU</Badge></div>
              {skus.length ? <div className="app-scrollbar overflow-x-auto"><div className="min-w-[620px] overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
                <div className="grid grid-cols-[1.4fr_1fr_1fr_1fr_1fr] bg-slate-50 px-3 py-2 text-[10px] font-bold text-slate-400 dark:bg-slate-800"><span>SKU</span><span>规格</span><span>售价（₽）</span><span>库存</span><span>状态</span></div>
                {skus.map((sku, index) => <div key={String(sku.id || sku.sku || index)} className="grid grid-cols-[1.4fr_1fr_1fr_1fr_1fr] items-center border-t border-slate-100 px-3 py-2.5 text-xs dark:border-slate-800">
                  <span className="font-mono text-[11px] text-slate-600 dark:text-slate-300">{sku.sku || `SKU-${index + 1}`}</span>
                  <span>{sku.name || [sku.color, sku.size].filter(Boolean).join(" / ") || "默认"}</span>
                  <Input aria-label={`${sku.sku || `SKU-${index + 1}`} 售价`} disabled={locked} className="h-8 w-24" type="number" min="0.01" step="0.01" value={String(sku.price ?? price)} onChange={(event) => updateSku(index, "price", event.target.value)} />
                  <Input aria-label={`${sku.sku || `SKU-${index + 1}`} 库存`} disabled={locked} className="h-8 w-20" type="number" min="0" step="1" value={String(sku.stock ?? 0)} onChange={(event) => updateSku(index, "stock", event.target.value)} />
                  <Badge tone={(sku.stock || 0) > 0 ? "emerald" : "rose"}>{(sku.stock || 0) > 0 ? "有货" : "缺货"}</Badge>
                </div>)}
              </div></div> : <EmptyState title="暂无 SKU 数据" description="返回商品详情确认来源规格是否采集完整。" />}
            </div>}

            {activeSection === "images" && <div>
              <div className="mb-4"><h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">商品图片</h3><p className="mt-0.5 text-xs text-slate-400">首张图片将作为 Ozon 主图，可用箭头调整顺序</p></div>
              <div className="mb-4 flex flex-col gap-2 sm:flex-row">
                <Input disabled={locked} aria-label="图片地址" value={imageUrl} onChange={(event) => { setImageUrl(event.target.value); setImageError(""); }} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addImage(); } }} placeholder="https://example.com/product.jpg" />
                <Button disabled={locked || !imageUrl.trim()} variant="secondary" onClick={addImage}><Plus className="h-4 w-4" />添加图片</Button>
              </div>
              {imageError && <p className="mb-3 text-xs text-rose-600">{imageError}</p>}
              {images.length ? <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{images.map((image, index) => <div key={image} className="group relative aspect-square overflow-hidden rounded-xl bg-slate-100 ring-1 ring-slate-200 dark:ring-slate-700">
                <img src={image} alt={`商品图片 ${index + 1}`} className="h-full w-full object-cover" />
                {index === 0 && <Badge className="absolute left-2 top-2 bg-slate-950/70 text-white ring-white/10">主图</Badge>}
                {!locked && <div className="absolute inset-x-2 bottom-2 flex justify-center gap-1 rounded-xl bg-slate-950/75 p-1 opacity-0 backdrop-blur-sm transition group-hover:opacity-100 group-focus-within:opacity-100">
                  <Button aria-label="图片前移" title="前移" size="icon" variant="ghost" className="h-7 w-7 text-white hover:bg-white/15 hover:text-white" disabled={index === 0} onClick={() => moveImage(index, -1)}><ArrowUp className="h-3.5 w-3.5" /></Button>
                  <Button aria-label="图片后移" title="后移" size="icon" variant="ghost" className="h-7 w-7 text-white hover:bg-white/15 hover:text-white" disabled={index === images.length - 1} onClick={() => moveImage(index, 1)}><ArrowDown className="h-3.5 w-3.5" /></Button>
                  <Button aria-label="删除图片" title="删除" size="icon" variant="ghost" className="h-7 w-7 text-white hover:bg-rose-500/80 hover:text-white" onClick={() => setImages((current) => current.filter((_, imageIndex) => imageIndex !== index))}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>}
              </div>)}</div> : <EmptyState title="暂无商品图片" description="从原始商品导入或手动添加图片后再执行 Mock 发布。" />}
            </div>}
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="p-5">
            <div className="flex items-center justify-between"><h2 className="text-sm font-bold text-slate-900 dark:text-white">Mock 发布检查</h2><span className={cn("text-sm font-bold", percent === 100 ? "text-emerald-600" : "text-amber-600")}>{percent}%</span></div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className={cn("h-full rounded-full transition-all", percent === 100 ? "bg-emerald-500" : "bg-amber-500")} style={{ width: `${percent}%` }} /></div>
            <div className="mt-4 space-y-2.5">{reviewChecks.map(([label, ready]) => <div key={label} className="flex items-center justify-between text-xs"><span className="text-slate-500">{label}</span>{ready ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <AlertTriangle className="h-4 w-4 text-amber-500" />}</div>)}</div>
          </Card>
          <Card className="p-5">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">定价摘要</h2>
            <div className="mt-4 rounded-xl bg-indigo-50 p-4 dark:bg-indigo-500/10"><p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-500">建议售价</p><div className="mt-1 flex items-end gap-2"><Input disabled={locked} className="h-10 max-w-32 border-indigo-200 bg-white text-lg font-bold text-indigo-700 dark:border-indigo-500/30 dark:bg-slate-900 dark:text-indigo-300" type="number" min="0.01" step="0.01" value={price} onChange={(event) => updateSku(0, "price", event.target.value)} /><span className="pb-2 text-xs font-semibold text-indigo-500">RUB</span></div></div>
            <div className="mt-4 flex items-center justify-between text-xs"><span className="text-slate-400">预计利润率</span><strong className="text-emerald-600">{formatPercent(draft.profit_margin)}</strong></div>
            <div className="mt-3 flex items-center justify-between text-xs"><span className="text-slate-400">定价规则</span><strong className="text-slate-700 dark:text-slate-200">默认俄罗斯站</strong></div>
          </Card>
          <Card className="border-blue-200 bg-blue-50/50 p-5 dark:border-blue-500/20 dark:bg-blue-500/5"><div className="flex gap-3"><ShieldCheck className="h-5 w-5 shrink-0 text-blue-600" /><div><h3 className="text-sm font-bold text-blue-800 dark:text-blue-200">安全发布模式</h3><p className="mt-1 text-xs leading-5 text-blue-700/70 dark:text-blue-300/70">当前使用 Mock Ozon Connector。确认发布会完整执行流程，但不会在真实 Ozon 店铺创建商品。</p></div></div></Card>
        </div>
      </div>

      <Dialog open={confirmOpen} title="确认执行 Mock 发布？" description="系统会保存当前修改并生成本地模拟发布结果，不会连接或修改真实 Ozon 店铺。" onClose={() => { setConfirmOpen(false); setAcknowledged(false); }}>
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><p className="line-clamp-2 text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</p><div className="mt-3 flex items-center justify-between text-xs"><span className="text-slate-400">售价</span><strong>{formatMoney(Number(price), "RUB")}</strong></div><div className="mt-2 flex items-center justify-between text-xs"><span className="text-slate-400">SKU</span><strong>{skus.length} 个</strong></div></div>
        <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-indigo-600" /><span>我已人工检查标题、描述、类目、属性、SKU、价格、库存和图片，确认只执行本地 Mock 发布。</span></label>
        <div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={() => setConfirmOpen(false)}>取消</Button><Button disabled={!acknowledged || publishing} onClick={() => void publish()}>{publishing ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}确认并 Mock 发布</Button></div>
      </Dialog>
    </div>
  );
}
