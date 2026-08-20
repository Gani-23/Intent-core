export function formatRelativeHours(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "n/a";
  }
  if (value < 1) {
    return `${Math.round(value * 60)}m`;
  }
  if (value < 24) {
    return `${value.toFixed(1)}h`;
  }
  return `${(value / 24).toFixed(1)}d`;
}

export function formatCount(value?: number | null) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value ?? 0);
}

export function formatDate(value?: string | null) {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function titleCase(value: string) {
  return value.replace(/[-_]/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function statusTone(status?: string | null) {
  const normalized = (status || "").toLowerCase();
  if (["passed", "ready", "healthy", "fresh", "trusted", "stable", "promote"].includes(normalized)) {
    return "good";
  }
  if (["warning", "due_soon", "aging", "degraded", "pending_review", "running"].includes(normalized)) {
    return "warn";
  }
  if (["critical", "failed", "blocked", "rejected", "overdue", "missing", "hold", "risky"].includes(normalized)) {
    return "bad";
  }
  return "neutral";
}
