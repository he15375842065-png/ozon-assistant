export type ID = number | string;

export type AiStatus = "pending" | "processing" | "completed" | "failed" | string;
export type OzonStatus = "not_created" | "draft" | "review" | "published" | "failed" | string;
export type DraftStatus = "draft" | "review" | "published" | "failed" | "stale";
export type TaskStatus = "pending" | "running" | "success" | "failed" | "cancelled" | string;
export type LogLevel = "INFO" | "WARNING" | "ERROR" | string;

export interface ProductVariant {
  id?: ID;
  source_sku_id?: string;
  internal_sku?: string;
  name?: string;
  color?: string;
  size?: string;
  purchase_price?: number;
  stock?: number;
  image?: string;
}

export interface AiResult {
  id?: ID;
  title_ru?: string;
  description_ru?: string;
  category_suggestion?: string;
  category_id?: string | number;
  attributes?: Record<string, unknown>;
  risks?: string[];
  provider?: string;
  model?: string;
  tokens?: number;
  duration_ms?: number;
  created_at?: string;
}

export interface Product {
  id: ID;
  data_kind?: "mock" | "real";
  data_provider?: string;
  source?: string;
  source_product_id?: string;
  source_url?: string;
  title_original?: string;
  title?: string;
  description_original?: string;
  category_original?: string;
  supplier?: string;
  purchase_price?: number;
  currency?: string;
  images?: string[];
  variants?: ProductVariant[];
  sku_count?: number;
  attributes?: Record<string, unknown>;
  stock?: number;
  ai_status?: AiStatus;
  ozon_status?: OzonStatus;
  estimated_price?: number;
  suggested_price?: number;
  estimated_margin?: number;
  profit_margin?: number;
  ai_result?: AiResult | null;
  created_at?: string;
  updated_at?: string;
}

export interface DashboardData {
  product_total: number;
  pending_ai: number;
  pending_review: number;
  published: number;
  task_counts?: Record<string, number>;
  recent_products?: Product[];
  recent_errors?: LogEntry[];
}

export interface DraftSku {
  id?: ID;
  sku?: string;
  name?: string;
  price?: number;
  stock?: number;
  color?: string;
  size?: string;
}

export interface Draft {
  id: ID;
  product_id?: ID;
  title_ru?: string;
  title?: string;
  description_ru?: string;
  description?: string;
  category_id?: string | number;
  category_name?: string;
  attributes?: Record<string, unknown>;
  images?: string[];
  skus?: DraftSku[];
  status?: DraftStatus;
  suggested_price?: number;
  price?: number;
  stock?: number;
  profit_margin?: number;
  updated_at?: string;
  created_at?: string;
}

export interface TaskItem {
  id: ID;
  type?: string;
  task_type?: string;
  status: TaskStatus;
  progress?: number;
  started_at?: string;
  ended_at?: string;
  created_at?: string;
  error?: string | null;
  retries?: number;
  message?: string;
}

export interface WorkflowResponse {
  product: Product;
  collection_mode?: "mock" | "real";
  task_id: ID;
  draft_id?: ID | null;
  message: string;
}

export interface SourceBrowserStatus {
  status: "closed" | "opened";
  message: string;
}

export interface PublishResponse {
  draft: Draft;
  task_id: ID;
  message: string;
}

export interface LogEntry {
  id: ID;
  level: LogLevel;
  module?: string;
  message: string;
  created_at?: string;
}

export interface AppSettings {
  source_provider: string;
  ai_provider: string;
  ai_model: string;
  ai_temperature: number;
  ai_base_url: string | null;
  ai_api_key_configured: boolean;
  ozon_mode: string;
  ozon_client_id_configured: boolean;
  ozon_api_key_configured: boolean;
  database_backend: string;
  exchange_rate: number;
  domestic_shipping: number;
  international_shipping: number;
  ozon_commission_rate: number;
  target_margin: number;
}

export interface AppSettingsUpdate {
  source_provider?: string;
  ai_provider?: string;
  ai_model?: string;
  ai_temperature?: number;
  ai_base_url?: string | null;
  ai_api_key?: string;
  ozon_mode?: string;
  ozon_client_id?: string;
  ozon_api_key?: string;
  exchange_rate?: number;
  domestic_shipping?: number;
  international_shipping?: number;
  ozon_commission_rate?: number;
  target_margin?: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}

export type ListResponse<T> = T[] | Paginated<T>;

export function listItems<T>(value: ListResponse<T> | undefined): T[] {
  if (!value) return [];
  return Array.isArray(value) ? value : value.items;
}

export function listTotal<T>(value: ListResponse<T> | undefined): number {
  if (!value) return 0;
  return Array.isArray(value) ? value.length : value.total;
}
