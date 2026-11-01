import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="PayPilot home">
          <Logo />
        </Link>
        <nav className="hidden items-center gap-5 text-[13px] text-fg-2 md:flex" aria-label="Site">
          <Link href="/#how" className="hover:text-fg">How it works</Link>
          <Link href="/#security" className="hover:text-fg">AgentShield</Link>
          <Link href="/architecture" className="hover:text-fg">Architecture</Link>
          <Link href="/demo" className="hover:text-fg">Guided demo</Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/dashboard">Console</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/command-center">
              Command Center <ArrowRight />
            </Link>
          </Button>
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-[13px] text-fg-3 sm:flex-row sm:items-center sm:px-6">
        <Logo className="text-fg" />
        <span>AI can reason. PayPilot decides if it can spend.</span>
        <span className="sm:ml-auto">Payments executed through PayPal. PayPilot is not affiliated with PayPal.</span>
      </div>
    </footer>
  );
}
