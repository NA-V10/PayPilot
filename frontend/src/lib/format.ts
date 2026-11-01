const LOCALE_FOR: Record<string, string> = { INR: "en-IN", USD: "en-US", EUR: "de-DE", GBP: "en-GB" };

export function money(amount: number | null | undefined, currency = "INR", opts: { compact?: boolean } = {}) {
  if (amount == null) return "—";
  const fractional = !Number.isInteger(amount);
  return new Intl.NumberFormat(LOCALE_FOR[currency] ?? "en-US", {
    style: "currency",
    currency,
    notation: opts.compact ? "compact" : "standard",
    minimumFractionDigits: fractional && !opts.compact ? 2 : 0,
    maximumFractionDigits: opts.compact ? 1 : 2,
  }).format(amount);
}

export function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  if (diff < 86400 * 30) return `${Math.round(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function clock(iso: string, withMs = false) {
  const d = new Date(iso);
  const t = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return withMs ? `${t}.${String(d.getMilliseconds()).padStart(3, "0")}` : t;
}

export function dateTime(iso: string) {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function shortDate(isoDate: string) {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function humanize(s: string | null | undefined) {
  if (!s) return "";
  return s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}
