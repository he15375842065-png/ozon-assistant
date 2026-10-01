import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell, type PageId, type ToastMessage } from "./components/AppShell";
import { api } from "./lib/api";
import type { Draft, Product } from "./lib/types";
import { DashboardPage } from "./pages/DashboardPage";
import { DraftReviewPage, DraftsPage } from "./pages/DraftsPages";
import { AiProcessingPage, CollectPage, ProductDetailPage, ProductLibraryPage } from "./pages/ProductsPages";
import { ComingSoonPage, LogsPage, SettingsPage, TasksPage } from "./pages/SystemPages";

const labels: Record<PageId, string> = {
  dashboard: "工作台",
  collect: "商品采集",
  products: "商品库",
  "product-detail": "商品详情",
  ai: "AI 加工",
  drafts: "Ozon 草稿",
  "draft-review": "草稿审核",
  tasks: "任务中心",
  logs: "运行日志",
  settings: "设置",
  coming: "开发中",
};

function initialTheme(): "light" | "dark" {
  const stored = localStorage.getItem("ozon-assistant-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function App() {
  const [page, setPage] = useState<PageId>("dashboard");
  const [pageLabel, setPageLabel] = useState(labels.dashboard);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedDraft, setSelectedDraft] = useState<Draft | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(initialTheme);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const toastId = useRef(0);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("ozon-assistant-theme", theme);
  }, [theme]);

  useEffect(() => {
    let alive = true;
    const check = () => api.health().then(() => { if (alive) setApiOnline(true); }).catch(() => { if (alive) setApiOnline(false); });
    void check();
    const interval = window.setInterval(() => void check(), 30_000);
    return () => { alive = false; window.clearInterval(interval); };
  }, []);

  const notify = useCallback((message: string, tone: "success" | "error" | "info" = "info") => {
    const id = ++toastId.current;
    setToasts((current) => [...current, { id, message, tone }].slice(-3));
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 3600);
  }, []);

  const navigate = useCallback((next: PageId, label?: string) => {
    setPage(next);
    setPageLabel(label || labels[next]);
  }, []);

  function openProduct(product: Product) {
    setSelectedProduct(product);
    navigate("product-detail", "商品详情");
  }

  function openDraft(draft: Draft) {
    setSelectedDraft(draft);
    navigate("draft-review", "草稿审核");
  }

  const commonProductProps = {
    onOpenProduct: openProduct,
    onNavigate: (target: "collect" | "products" | "ai" | "drafts" | "tasks") => navigate(target),
    notify,
  };

  let content: React.ReactNode;
  switch (page) {
    case "dashboard": content = <DashboardPage onNavigate={navigate} onOpenProduct={openProduct} />; break;
    case "collect": content = <CollectPage {...commonProductProps} />; break;
    case "products": content = <ProductLibraryPage {...commonProductProps} />; break;
    case "product-detail": content = selectedProduct ? <ProductDetailPage product={selectedProduct} onNavigate={commonProductProps.onNavigate} notify={notify} /> : <ProductLibraryPage {...commonProductProps} />; break;
    case "ai": content = <AiProcessingPage {...commonProductProps} />; break;
    case "drafts": content = <DraftsPage onOpenDraft={openDraft} onNavigateProducts={() => navigate("products")} />; break;
    case "draft-review": content = selectedDraft ? <DraftReviewPage draft={selectedDraft} onBack={() => navigate("drafts")} notify={notify} onPublished={() => navigate("drafts")} /> : <DraftsPage onOpenDraft={openDraft} onNavigateProducts={() => navigate("products")} />; break;
    case "tasks": content = <TasksPage notify={notify} onNavigateLogs={() => navigate("logs")} />; break;
    case "logs": content = <LogsPage />; break;
    case "settings": content = <SettingsPage notify={notify} />; break;
    case "coming": content = <ComingSoonPage label={pageLabel} onBack={() => navigate("dashboard")} />; break;
    default: content = <DashboardPage onNavigate={navigate} onOpenProduct={openProduct} />;
  }

  return <AppShell activePage={page} activeLabel={pageLabel} onNavigate={navigate} theme={theme} onToggleTheme={() => setTheme((value) => value === "dark" ? "light" : "dark")} apiOnline={apiOnline} toasts={toasts}>{content}</AppShell>;
}

export default App;
