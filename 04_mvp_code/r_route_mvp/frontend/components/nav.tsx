"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, caseStore } from "@/lib/api";
import { cn } from "./ui/primitives";

const TABS = [["/", "Overview"], ["/analyze", "AI 분석"], ["/vision", "Vision 판독"], ["/map", "Live Map"], ["/engine", "Optimizer"], ["/verify", "Hub 검수"], ["/impact", "Impact"]];

export function Nav() {
  const path = usePathname();
  const router = useRouter();
  async function reset() { try { await api.reset(); } finally { caseStore.clear(); router.push("/analyze"); router.refresh(); } }
  return (
    <header className="sticky top-0 z-50 border-b border-black/[.06] bg-canvas/70 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-[1180px] items-center gap-4 px-4">
        <Link href="/" className="flex items-center gap-2.5 font-bold">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden><rect width="26" height="26" rx="8" fill="#0B1513" /><path d="M7 17c0-5 3-8 8-8h3" stroke="#34D399" strokeWidth="2.4" fill="none" strokeLinecap="round" /><path d="M16 6l3 3-3 3" stroke="#34D399" strokeWidth="2.4" fill="none" strokeLinecap="round" /><circle cx="7" cy="19" r="2" fill="#fff" /></svg>
          R_ROUTE
        </Link>
        <nav className="flex min-w-0 flex-1 gap-0.5 overflow-x-auto">
          {TABS.map(([href, label]) => (
            <Link key={href} href={href} className={cn("whitespace-nowrap rounded-full px-3 py-1.5 text-[13.5px] text-ink2 hover:bg-black/[.04]", path === href && "bg-ink text-white hover:bg-ink")}>{label}</Link>
          ))}
        </nav>
        <button onClick={reset} title="시드 데이터와 분석 기록을 처음 상태로 되돌립니다" className="whitespace-nowrap rounded-full border border-black/10 bg-white px-3 py-2 text-[12.5px] text-ink2">데모 초기화</button>
        <Link href="/analyze" className="whitespace-nowrap rounded-full bg-brand px-4 py-2 text-[13.5px] font-semibold text-white">▶ 데모 시작</Link>
      </div>
    </header>
  );
}
