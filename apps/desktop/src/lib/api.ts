import type {
  AppSettings,
  AppSettingsUpdate,
  DashboardData,
  Draft,
  ListResponse,
  LogEntry,
  OzonCategory,
  OzonCategoryAttribute,
  PublishResponse,
  Product,
  SourceBrowserStatus,
  TaskItem,
  WorkflowResponse,
} from "./types";

const configuredUrl = import.meta.env.VITE_API_URL as string | undefined;
export const API_URL = (configuredUrl || "http://127.0.0.1:8001/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

type QueryValue = string | number | boolean | null | undefined;

function url(path: string, query?: Record<string, QueryValue>) {
  const endpoint = new URL(`${API_URL}${path.startsWith("/") ? path : `/${path}`}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") endpoint.searchParams.set(key, String(value));
    });
  }
  return endpoint.toString();
}

async function request<T>(path: string, init?: RequestInit, query?: Record<string, QueryValue>): Promise<T> {
  const response = await fetch(url(path, query), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = responseErrorMessage(payload, response.status);
    throw new ApiError(message, response.status, payload);
  }
  return payload as T;
}

function responseErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "string" && payload.trim()) return payload;
  if (!payload || typeof payload !== "object") return `请求失败 (${status})`;

  const body = payload as {
    detail?: unknown;
    message?: unknown;
    error?: unknown;
  };
  if (typeof body.error === "object" && body.error !== null) {
    const nestedMessage = (body.error as { message?: unknown }).message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) return nestedMessage;
  }
  if (typeof body.error === "string" && body.error.trim()) return body.error;
  if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  if (Array.isArray(body.detail) && body.detail.length > 0) {
    const validationMessage = body.detail
      .map((item) => item && typeof item === "object" && "msg" in item ? String(item.msg) : "")
      .filter(Boolean)
      .join("；");
    if (validationMessage) return validationMessage;
  }
  if (typeof body.message === "string" && body.message.trim()) return body.message;
  return `请求失败 (${status})`;
}

export const api = {
  health: () => request<{ status?: string; service?: string }>("/health"),
  sourceBrowserStatus: () => request<SourceBrowserStatus>("/sources/1688/browser/status"),
  openSourceBrowser: (sourceUrl?: string) => request<SourceBrowserStatus>("/sources/1688/browser/open", {
    method: "POST",
    body: JSON.stringify(sourceUrl ? { url: sourceUrl } : {}),
  }),
  dashboard: () => request<DashboardData>("/dashboard"),
  collectProduct: (sourceUrl: string, mode: "real" | "mock" = "real") =>
    request<WorkflowResponse>("/products/collect", {
      method: "POST",
      body: JSON.stringify({ url: sourceUrl, mode }),
    }),
  products: (query?: { search?: string; ai_status?: string; ozon_status?: string; page?: number; page_size?: number }) =>
    request<ListResponse<Product>>("/products", undefined, query),
  product: (id: Product["id"]) => request<Product>(`/products/${id}`),
  updateProduct: (id: Product["id"], data: Partial<Product>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteProduct: (id: Product["id"]) => request<void>(`/products/${id}`, { method: "DELETE" }),
  processProduct: (id: Product["id"]) =>
    request<WorkflowResponse>(`/products/${id}/process`, { method: "POST" }),
  drafts: (status?: string) => request<ListResponse<Draft>>("/drafts", undefined, { status }),
  draft: (id: Draft["id"]) => request<Draft>(`/drafts/${id}`),
  updateDraft: (id: Draft["id"], data: Partial<Draft>) =>
    request<Draft>(`/drafts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  publishDraft: (id: Draft["id"]) =>
    request<PublishResponse>(`/drafts/${id}/publish`, {
      method: "POST",
      body: JSON.stringify({ confirmed: true }),
    }),
  tasks: (query?: { status?: string; task_type?: string; limit?: number }) =>
    request<ListResponse<TaskItem>>("/tasks", undefined, query),
  cancelTask: (id: TaskItem["id"]) => request<TaskItem>(`/tasks/${id}/cancel`, { method: "POST" }),
  logs: (query?: { level?: string; module?: string; limit?: number }) =>
    request<ListResponse<LogEntry>>("/logs", undefined, query),
  settings: () => request<AppSettings>("/settings"),
  updateSettings: (data: AppSettingsUpdate) =>
    request<AppSettings>("/settings", { method: "PATCH", body: JSON.stringify(data) }),
  checkAiConnection: (data: { base_url?: string | null; api_key?: string; model?: string | null }) =>
    request<{ ok: boolean; base_url: string; model: string; verified: boolean; models: string[] }>(
      "/settings/ai/check",
      { method: "POST", body: JSON.stringify(data) },
    ),
  checkOzonConnection: (data: { client_id?: string; api_key?: string }) =>
    request<{ ok: boolean; items_returned: number }>(
      "/settings/ozon/check",
      { method: "POST", body: JSON.stringify(data) },
    ),
  syncOzonCategories: () =>
    request<{ categories: number }>("/ozon/categories/sync", { method: "POST" }),
  searchOzonCategories: (q: string, limit = 20) =>
    request<OzonCategory[]>("/ozon/categories", undefined, { q, limit }),
  syncOzonCategoryAttributes: (categoryId: number) =>
    request<{ category_id: number; attributes: number; required: number }>(
      `/ozon/categories/${categoryId}/attributes/sync`,
      { method: "POST" },
    ),
  ozonCategoryAttributes: (categoryId: number) =>
    request<OzonCategoryAttribute[]>(`/ozon/categories/${categoryId}/attributes`),
};

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "发生未知错误，请稍后重试";
}
