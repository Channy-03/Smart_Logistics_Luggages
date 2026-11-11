"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, useCaseId, won, type MatchRun, type Network } from "@/lib/api";
import { Badge, Button, Card, PageHead } from "@/components/ui/primitives";

const LiveMap = dynamic(() => import("@/components/live-map"), { ssr: false, loading: () => <div className="grid h-[560px] place-items-center text-ink3">지도 불러오는 중…</div> });

const Legend = () => (
  <div className="flex flex-wrap gap-3 text-xs text-ink2">
    <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[#F59E0B]" />출발(반품)</span>
    <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full bg-ink" />허브</span>
    <span className="flex items-center gap-1.5"><i className="inline-block h-1 w-5 rounded bg-brand" />확정 경로</span>
    <span className="flex items-center gap-1.5"><i className="inline-block h-0 w-5 border-t-2 border-dashed border-[#A7B3B0]" />후보(선택 안 됨)</span>
  </div>
);

export default function MapPage() {
  const [net, setNet] = useState<Network>();
  const [run, setRun] = useState<MatchRun>();
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"mine" | "city">("mine");
  const rid = useCaseId();
  const load = useCallback(() => api.network().then(setNet).catch(() => undefined), []);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  async function match() { setBusy(true); try { setRun(await api.runMatch(false, true)); await load(); } finally { setBusy(false); } }
  const mine = net?.matches.find(m => m.return_id === rid);
  const hasMine = !!net?.returns.find(r => r.return_id === rid);
  const effMode = hasMine ? mode : "city";

  return (
    <>
      <PageHead eyebrow="ATP Inventory · Matching Engine" title={effMode === "mine" ? "내 반품이 다음 구매자에게 가는 길" : "창원시 전체 매칭 현황"}
        sub={effMode === "mine" ? "내 반품, 검수할 허브, 같은 상품을 기다리는 주문만 보여줍니다. 나머지는 회색으로 물렸습니다." : "허브 10곳의 이동 중 재고와 열린 주문을 Min Cost Flow로 배정한 결과입니다."}
        right={<span className="font-mono text-xs text-ink3">5초마다 서버에서 다시 읽음</span>} />
      <div className="grid gap-4 lg:grid-cols-[1.9fr_1fr]">
        <Card className="relative overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-black/[.06] px-4 py-3">
            <div className="flex gap-1.5">
              {(["mine", "city"] as const).map(m => (
                <button key={m} disabled={m === "mine" && !hasMine} onClick={() => setMode(m)}
                  className={`rounded-full px-3 py-1.5 text-[13px] disabled:opacity-40 ${effMode === m ? "bg-ink text-white" : "border border-black/10 bg-white"}`}>{m === "mine" ? "내 반품" : "도시 전체"}</button>
              ))}
            </div>
            <Legend />
          </div>
          {net ? <LiveMap net={net} focus={rid} mode={effMode} /> : <div className="grid h-[560px] place-items-center text-ink3">API 연결 대기 (localhost:8000)</div>}
          {effMode === "mine" && mine && (
            <div className="absolute bottom-4 right-4 z-[500] rounded-xl border border-black/10 bg-white/95 px-4 py-2.5 text-right shadow">
              <div className="font-semibold">기존 경로 대비 −{Math.round(mine.km_saved)}km</div>
              <div className="text-xs text-ink3">수도권 창고 왕복 없음 · −{won(mine.cost_saved)}원</div>
            </div>
          )}
        </Card>
        <div className="grid content-start gap-3.5">
          {!hasMine && <Card className="p-4 text-sm text-ink2">아직 내 반품이 없어요. <Link href="/analyze" className="font-semibold text-brand">AI 분석</Link>에서 반품을 접수하면 그 반품의 경로만 따로 볼 수 있어요.</Card>}
          {hasMine && !mine && <Card className="p-4 text-sm"><b>같은 상품을 기다리는 주문을 찾고 있어요.</b><div className="text-ink2">매칭이 정해지면 초록 경로로 표시돼요. 최대 72시간 동안 허브에서 기다리고, 없으면 판매자 창고로 보내요. 이때 비용은 기존 방식과 같아요.</div>
            <Button className="mt-3" onClick={match} disabled={busy}>{busy ? "최적화 중…" : "지금 매칭 실행"}</Button></Card>}
          {mine && <Card className="border-[#9FE3C6] bg-[#F2FCF7] p-4 text-sm"><b>{rid} → {mine.order_id}</b><br />허브에서 구매자까지 {mine.km_hub_buyer.toFixed(1)}km · 절감 <b className="font-mono">{won(mine.cost_saved)}원</b> · CO₂ −{mine.co2_saved.toFixed(2)}kg
            <div className="mt-2"><Link href="/verify" className="font-semibold text-brand">허브 검수로 →</Link></div></Card>}
          <Card className="p-4">
            <div className="flex items-center justify-between"><b className="text-sm">매칭 기록</b>{run && <span className="font-mono text-[11px] text-ink3">{run.run_id}</span>}</div>
            <div className="mt-2 grid max-h-[340px] gap-2 overflow-auto">
              <AnimatePresence>{net?.matches.map(m => (
                <motion.div key={m.return_id} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                  className={`grid grid-cols-[1fr_auto] items-center gap-2 rounded-xl border bg-white p-2.5 text-[13px] ${m.return_id === rid ? "border-[#9FE3C6]" : "border-black/[.06]"}`}>
                  <div><span className="font-mono text-[11px] text-ink3">{m.return_id}</span><div>{m.hub_id} → {m.order_id} · {m.km_hub_buyer.toFixed(1)}km</div></div>
                  <span className="font-mono font-semibold text-[#06694A]">+{won(m.cost_saved)}</span>
                </motion.div>))}</AnimatePresence>
              {net && net.matches.length === 0 && <p className="text-sm text-ink3">아직 확정된 매칭이 없어요.</p>}
            </div>
          </Card>
          {effMode === "mine" && <Badge tone="gray" className="justify-self-start">후보 번호는 허브에서 가까운 순서예요. 확정은 전체 비용으로 정해요.</Badge>}
        </div>
      </div>
    </>
  );
}
