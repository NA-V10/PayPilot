import { cn } from "@/lib/utils";

/** Shield silhouette + a navigation chevron that doubles as a payment "pass" mark. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={cn("size-7", className)} aria-hidden>
      <path d="M16 2.5 27 6.6v8.2c0 7-4.6 12.3-11 14.7C9.6 27.1 5 21.8 5 14.8V6.6L16 2.5Z" className="fill-fg" />
      <path d="M11 20.5 16 9l5 11.5-5-2.6-5 2.6Z" className="fill-bg" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight">PayPilot</span>
    </span>
  );
}
