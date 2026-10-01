import type { ReactNode } from "react";
import {
  BarChart3,
  Bell,
  Bot,
  Boxes,
  ChevronDown,
  ClipboardCheck,
  CloudCog,
  Database,
  FileClock,
  HelpCircle,
  LayoutDashboard,
  ListChecks,
  Logs,
  Moon,
  PackageCheck,
  PackageOpen,
  PlusCircle,
  SearchCheck,
  Settings,
  ShoppingBag,
  Sparkles,
  Sun,
  WandSparkles,
  Zap,
} from "lucide-react";
import { API_URL } from "../lib/api";
import { Button, cn } from "./ui";

export type PageId =
  | "dashboard"
  | "collect"
  | "products"
  | "product-detail"
  | "ai"
  | "drafts"
  | "draft-review"
  | "tasks"
  | "logs"
  | "settings"
  | "coming";

interface NavItem {
  id: PageId;
  label: string;
  icon: typeof LayoutDashboard;
  badge?: string;
  coming?: boolean;
}

const groups: Array<{ label?: string; items: NavItem[] }> = [
  { items: [{ id: "dashboard", label: "工作台", icon: LayoutDashboard }] },
  {
    label: "商品运营",
    items: [
      { id: "collect", label: "商品采集", icon: PlusCircle },
      { id: "products", label: "商品库", icon: Boxes },
      { id: "ai", label: "AI 加工", icon: WandSparkles },
      { id: "drafts", label: "Ozon 草稿", icon: ClipboardCheck },
      { id: "coming", label: "已上架", icon: PackageCheck, coming: true },
    ],
  },
  {
    label: "增长中心",
    items: [
      { id: "coming", label: "选品中心", icon: SearchCheck, coming: true },
      { id: "coming", label: "库存与价格", icon: CloudCog, coming: true },
      { id: "coming", label: "订单管理", icon: ShoppingBag, coming: true },
      { id: "coming", label: "经营分析", icon: BarChart3, coming: true },
      { id: "coming", label: "AI 助手", icon: Bot, coming: true },
    ],
  },
  {
    label: "系统",
    items: [
      { id: "tasks", label: "任务中心", icon: ListChecks },
      { id: "logs", label: "运行日志", icon: Logs },
      { id: "settings", label: "设置", icon: Settings },
    ],
  },
];

export interface ToastMessage {
  id: number;
  message: string;
  tone?: "success" | "error" | "info";
}

interface AppShellProps {
  activePage: PageId;
  activeLabel: string;
  onNavigate: (page: PageId, label?: string) => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  apiOnline: boolean | null;
  children: ReactNode;
  toasts?: ToastMessage[];
}

export function AppShell({ activePage, activeLabel, onNavigate, theme, onToggleTheme, apiOnline, children, toasts = [] }: AppShellProps) {
  return (
    <div className="h-screen min-h-[640px] bg-[#f6f7fb] text-slate-900 dark:bg-[#080d18] dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-40 flex w-[var(--sidebar-width)] flex-col border-r border-slate-200/80 bg-white px-3 py-4 transition-[width] dark:border-slate-800 dark:bg-slate-950">
        <button className="mb-5 flex h-12 items-center gap-3 rounded-xl px-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500" aria-label="返回工作台" onClick={() => onNavigate("dashboard")}>
          <span className="relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-[14px] bg-gradient-to-br from-indigo-500 via-indigo-600 to-violet-700 text-white shadow-lg shadow-indigo-600/20">
            <PackageOpen className="h-5 w-5" />
            <span className="absolute -bottom-3 -right-3 h-7 w-7 rounded-full bg-white/20" />
          </span>
          <span className="min-w-0 lg:block max-lg:hidden">
            <span className="block truncate text-[15px] font-extrabold tracking-tight text-slate-950 dark:text-white">ozon助手</span>
            <span className="block truncate text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400">Seller operations</span>
          </span>
        </button>

        <nav className="app-scrollbar flex-1 overflow-y-auto overflow-x-hidden" aria-label="主导航">
          {groups.map((group, groupIndex) => (
            <div key={group.label || groupIndex} className="mb-4">
              {group.label && <div className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400 max-lg:text-center max-lg:px-0"> <span className="max-lg:hidden">{group.label}</span><span className="hidden max-lg:inline">·</span></div>}
              <div className="space-y-0.5">
                {group.items.map((item, itemIndex) => {
                  const isActive = activePage === item.id && (!item.coming || activeLabel === item.label);
                  const Icon = item.icon;
                  return (
                    <button
                      key={`${item.label}-${itemIndex}`}
                      title={item.label}
                      onClick={() => onNavigate(item.id, item.label)}
                      className={cn(
                        "group relative flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40 max-lg:justify-center max-lg:px-0",
                        isActive
                          ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100",
                      )}
                    >
                      {isActive && <span className="absolute inset-y-2 -left-3 w-0.5 rounded-r-full bg-indigo-600 dark:bg-indigo-400" />}
                      <Icon className={cn("h-[18px] w-[18px] shrink-0", isActive && "text-indigo-600 dark:text-indigo-400")} />
                      <span className="truncate max-lg:hidden">{item.label}</span>
                      {item.coming && <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-400 dark:bg-slate-800 max-lg:hidden">开发中</span>}
                      {!item.coming && item.badge && <span className="ml-auto grid min-w-5 place-items-center rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300 max-lg:absolute max-lg:right-1 max-lg:top-1 max-lg:h-2 max-lg:min-w-2 max-lg:p-0 max-lg:text-transparent">{item.badge}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
          <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900 max-lg:bg-transparent max-lg:p-1">
            <div className="flex items-center gap-2.5 max-lg:justify-center">
              <span className="relative grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-indigo-600 shadow-sm ring-1 ring-slate-200 dark:bg-slate-800 dark:text-indigo-300 dark:ring-slate-700"><Database className="h-4 w-4" /></span>
              <div className="min-w-0 flex-1 max-lg:hidden">
                <p className="truncate text-[11px] font-semibold text-slate-700 dark:text-slate-200">本地工作空间</p>
                <p className="truncate text-[10px] text-slate-400">SQLite · 单店铺</p>
              </div>
              <ChevronDown className="h-3.5 w-3.5 text-slate-400 max-lg:hidden" />
            </div>
          </div>
        </div>
      </aside>

      <div className="ml-[var(--sidebar-width)] flex h-screen min-w-0 flex-col transition-[margin]">
        <header className="z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/90 px-5 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-950/85 sm:px-7">
          <div className="flex min-w-0 items-center gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">{activeLabel}</p>
              <p className="hidden truncate text-[11px] text-slate-400 sm:block">Ozon 店铺 · 俄罗斯站</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <div title="当前仅执行本地模拟流程，不连接真实 Ozon 店铺" className="mr-1 hidden items-center rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-[10px] font-bold text-violet-700 dark:border-violet-500/25 dark:bg-violet-500/10 dark:text-violet-300 sm:flex">
              MOCK 模式
            </div>
            <div title={API_URL} className="mr-2 hidden items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 md:flex">
              <span className={cn("h-1.5 w-1.5 rounded-full", apiOnline === true ? "bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,.12)]" : apiOnline === false ? "bg-amber-500 shadow-[0_0_0_3px_rgba(245,158,11,.12)]" : "animate-pulse bg-slate-400")} />
              {apiOnline === true ? "本地服务正常" : apiOnline === false ? "预览模式" : "正在连接"}
            </div>
            <Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label={theme === "dark" ? "切换浅色主题" : "切换深色主题"} title={theme === "dark" ? "切换浅色主题" : "切换深色主题"}>
              {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
            </Button>
            <Button variant="ghost" size="icon" aria-label="帮助" title="帮助中心" className="max-sm:hidden" onClick={() => onNavigate("coming", "帮助中心")}><HelpCircle className="h-[18px] w-[18px]" /></Button>
            <Button variant="ghost" size="icon" aria-label="查看任务通知" title="任务通知" onClick={() => onNavigate("tasks")}>
              <Bell className="h-[18px] w-[18px]" />
            </Button>
            <button className="ml-1 hidden h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 text-xs font-bold text-white shadow-sm sm:grid" aria-label="打开工作空间设置" title="个人工作空间" onClick={() => onNavigate("settings")}>HZ</button>
          </div>
        </header>

        <main className="app-scrollbar min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1680px] p-5 sm:p-7">{children}</div>
        </main>
      </div>

      <div className="pointer-events-none fixed bottom-5 right-5 z-[90] flex w-[min(380px,calc(100vw-2.5rem))] flex-col gap-2" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className={cn("pointer-events-auto flex items-center gap-3 rounded-xl border bg-white px-4 py-3 text-sm font-medium shadow-xl shadow-slate-950/10 dark:bg-slate-900", toast.tone === "error" ? "border-rose-200 text-rose-700 dark:border-rose-500/30 dark:text-rose-300" : toast.tone === "success" ? "border-emerald-200 text-emerald-700 dark:border-emerald-500/30 dark:text-emerald-300" : "border-slate-200 text-slate-700 dark:border-slate-700 dark:text-slate-200")}>
            {toast.tone === "success" ? <Zap className="h-4 w-4" /> : toast.tone === "error" ? <FileClock className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
}
