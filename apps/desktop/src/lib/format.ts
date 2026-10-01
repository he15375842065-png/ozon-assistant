export function formatMoney(value?: number, currency = "CNY") {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  if (currency === "RUB") return `₽${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value)}`;
  return `¥${new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(value)}`;
}

export function formatPercent(value?: number, maximumFractionDigits = 2) {
  if (value === undefined || value === null || !Number.isFinite(value)) return "—";
  const percentage = Math.abs(value) <= 1 ? value * 100 : value;
  return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits }).format(percentage)}%`;
}

export function formatDate(value?: string, includeTime = true) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

export function relativeTime(value?: string) {
  if (!value) return "刚刚";
  const delta = Date.now() - new Date(value).getTime();
  if (Number.isNaN(delta)) return value;
  const minutes = Math.max(1, Math.floor(delta / 60000));
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function statusLabel(status?: string) {
  const labels: Record<string, string> = {
    pending: "等待中",
    processing: "处理中",
    running: "运行中",
    completed: "已完成",
    success: "成功",
    failed: "失败",
    cancelled: "已取消",
    not_created: "未建草稿",
    draft: "草稿",
    review: "待审核",
    published: "Mock 已发布",
    stale: "需重新生成",
    INFO: "信息",
    WARNING: "警告",
    ERROR: "错误",
  };
  return status ? labels[status] || status : "未知";
}
