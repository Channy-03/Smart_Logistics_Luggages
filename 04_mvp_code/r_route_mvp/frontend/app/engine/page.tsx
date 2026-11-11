"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api, useCaseId, won, type CounterExample, type MatchRun } from "@/lib/api";
import { Button, Card, PageHead } from "@/components/ui/primitives";

// 반례: '가장 가까운 순서' vs '최소비용 흐름'. 같은 4개 지점에 두 방식의 배정을 나란히 그린다.
function CounterExampleCard() {
  const [cx, setCx] = useState<CounterExample>();
  const [err, setErr] = useState("");
  useEffect(() => { api.counterexample().then(setCx).catch(e => setErr(String(e))); }, []);
  if (err) return <Card className="text-sm text-red-600">반례를 불러오지 못했어요: {err}</Card>;
  if (!cx) return null;
  const pts = [...cx.hubs.map(h => ({ id: h.hub_id, lat: h.lat, lng: h.lng })), ...cx.orders.map(o => ({ id: o.order_id, lat: o.lat, lng: o.lng }))];
  const lat0 = Math.min(...pts.map(p => p.lat)), lat1 = Math.max(...pts.map(p => p.lat)), lng0 = Math.min(...pts.map(p => p.lng)), lng1 = Math.max(...pts.map(p => p.lng));
  const X = (lng: number) => 30 + (lng - lng0) / (lng1 - lng0) * 230, Y = (lat: number) => 160 - (lat - lat0) / (lat1 - lat0) * 110;
  const hubOf = (rid: string) => cx.hubs.find(h => h.hub_id === cx.returns.find(r => r.return_id === rid)!.hub_id)!;
  const ord = (oid: string) => cx.orders.find(o => o.order_id === oid)!;
  const name: Record<string, string> = { "RT-CX-A": "반품 A", "RT-CX-B": "반품 B", "OD-CX-P": "주문 P", "OD-CX-Q": "주문 Q" };
  const legText = (l: CounterExample["nearest_first"]["legs"][number]) =>
    l.kind === "reallocate" ? `${name[l.from]} → ${name[l.to]} · ${l.km.toFixed(1)}km`
      : l.kind === "seller_return" ? `${name[l.from]} → 수도권 판매자 창고 · ${l.km}km (반경 안에 남은 주문 없음)`
        : `수도권 신규 재고 → ${name[l.to]} · ${l.km}km`;
  const Panel = ({ title, plan, good }: { title: string; plan: CounterExample["nearest_first"]; good: boolean }) => (
    <div className={`rounded-2xl border p-3 ${good ? "border-brand" : "border-black/[.08]"}`}>
      <div className="flex items-baseline justify-between gap-2"><b className="text-sm">{title}</b><span className={`font-mono text-lg ${good ? "text-brand" : "text-ink2"}`}>{won(plan.total_cost)}원</span></div>
      <svg viewBox="0 0 320 190" className="mt-1 h-auto w-full" role="img" aria-label={title}>
        <defs><marker id={`ar-${good}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#D1453B" /></marker></defs>
        {plan.legs.map(l => {
          if (l.kind === "reallocate") { const h = hubOf(l.from), o = ord(l.to); return <line key={l.from} x1={X(h.lng)} y1={Y(h.lat)} x2={X(o.lng)} y2={Y(o.lat)} stroke={good ? "#0E9F6E" : "#8A9894"} strokeWidth={3} />; }
          if (l.kind === "seller_return") { const h = hubOf(l.from); return <g key={l.from + "s"}><line x1={X(h.lng)} y1={Y(h.lat)} x2={X(h.lng) + 18} y2={36} stroke="#D1453B" strokeWidth={2} strokeDasharray="5 4" markerEnd={`url(#ar-${good})`} /><text x={X(h.lng) + 22} y={34} fontSize={10.5} fill="#B23A31">수도권 창고로 300km</text></g>; }
          const o = ord(l.to); return <g key={l.to + "n"}><line x1={X(o.lng) + 20} y1={16} x2={X(o.lng) + 4} y2={Y(o.lat) - 9} stroke="#D1453B" strokeWidth={2} strokeDasharray="5 4" markerEnd={`url(#ar-${good})`} /><text x={X(o.lng) + 24} y={14} textAnchor="end" fontSize={10.5} fill="#B23A31">수도권 신규 재고 300km</text></g>;
        })}
        {cx.hubs.map(h => <g key={h.hub_id}><rect x={X(h.lng) - 7} y={Y(h.lat) - 7} width={14} height={14} rx={3} fill="#0B1513" transform={`rotate(45 ${X(h.lng)} ${Y(h.lat)})`} /><text x={X(h.lng)} y={Y(h.lat) + 22} textAnchor="middle" fontSize={11} fill="#0B1513">{name[cx.returns.find(r => r.hub_id === h.hub_id)!.return_id]}</text></g>)}
        {cx.orders.map(o => <g key={o.order_id}><circle cx={X(o.lng)} cy={Y(o.lat)} r={7} fill="#fff" stroke="#0B1513" strokeWidth={2} /><text x={X(o.lng) + 11} y={Y(o.lat) + 4} fontSize={11} fill="#0B1513">{name[o.order_id]}</text></g>)}
      </svg>
      <div className="space-y-0.5 text-xs text-ink2">{plan.legs.map(l => <div key={l.from + l.to} className={l.kind === "reallocate" ? "" : "text-[#B23A31]"}>{legText(l)}</div>)}<div>총 이동거리 <b className="font-mono">{plan.km.toFixed(1)}km</b></div></div>
    </div>
  );
  return (
    <Card className="mt-4">
      <div className="mb-3"><b>가장 가까운 주문으로 보내면 안 되나요?</b><p className="mt-1 text-sm text-ink2">{cx.explanation} (반품 A 14:02, 반품 B 14:05 접수 · 매칭 반경 {cx.radius_km}km)</p></div>
      <div className="grid gap-3 md:grid-cols-2">
        <Panel title="들어온 순서대로 가장 가까운 주문" plan={cx.nearest_first} good={false} />
        <Panel title="R_ROUTE 최소비용 흐름" plan={cx.min_cost_flow} good />
      </div>
      <p className="mt-3 text-sm">같은 반품 2개, 주문 2개인데 최소비용 흐름이 비용을 <b className="font-mono">{won(cx.nearest_first.total_cost)}원 → {won(cx.min_cost_flow.total_cost)}원</b>으로, 이동거리를 <b className="font-mono">{Math.round(cx.nearest_first.km)}km → {Math.round(cx.min_cost_flow.km)}km</b>로 줄였어요. 각 반품만 보면 더 먼 주문으로 갔지만, 둘 다 수도권으로 돌아가지 않게 됐어요.</p>
    </Card>
  );
}

// 내 반품을 중심으로 한 부분 네트워크를 그린다 (전체 그래프는 표로)
export default function Engine() {
  const [res, setRes] = useState<MatchRun>();
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  async function commit() { await api.runMatch(false, true); router.push("/map"); }
  async function solve() { setBusy(true); try { setRes(await api.runMatch(true, false)); } finally { setBusy(false); } }

  const rid = useCaseId();
  const arcs = res?.graph?.arcs ?? [];
  const focusR = arcs.some(a => a.from === rid) ? rid : arcs.find(a => a.kind === "reallocate" && a.flow)?.from;
  const mine = arcs.filter(a => a.from === focusR).sort((a, b) => a.cost - b.cost).slice(0, 5);
  const targets = mine.map(a => a.to);
  const H = 90 + targets.length * 80;
  const y = (i: number) => 60 + i * 80;

  return (
    <>
      <PageHead eyebrow="Min Cost Flow Optimizer" title="왜 이 구매자인가"
        sub="반품·신규재고·주문·판매자복귀를 하나의 네트워크로 놓고 OR-Tools SimpleMinCostFlow로 총비용 최소 흐름을 찾습니다. 매칭이 없어도 해가 존재해 기존보다 나빠지지 않습니다."
        right={<Button onClick={solve} disabled={busy}>{busy ? "계산 중…" : "최적화 실행 (dry-run)"}</Button>} />
      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <Card>
          {!res || !mine.length ? <div className="grid h-80 place-items-center text-center text-ink3">{res ? "배정 대기 중인 반품이 없습니다. AI 분석에서 반품을 새로 접수하세요." : "최적화 실행을 누르면 네트워크가 그려집니다"}</div> : (
            <svg viewBox={`0 0 720 ${H}`} className="h-auto w-full" role="img" aria-label="최소비용 흐름 네트워크">
              <g transform={`translate(110,${H / 2})`}><rect x={-80} y={-24} width={160} height={48} rx={12} fill="#F59E0B" fillOpacity={.12} stroke="#F59E0B" /><text textAnchor="middle" y={5} fontSize={12.5} fontWeight={600}>{focusR}</text></g>
              {mine.map((a, i) => {
                const win = a.flow > 0;
                return (
                  <g key={a.to}>
                    <motion.path d={`M190 ${H / 2} C 330 ${H / 2}, 360 ${y(i)}, 470 ${y(i)}`} fill="none" stroke={win ? "#0E9F6E" : "#D3DBD8"} strokeWidth={win ? 3.4 : 1.4}
                      initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: i * .15, duration: .6 }} />
                    <text x={400} y={y(i) - 8} fontSize={11} fontFamily="var(--font-mono)" fill={win ? "#06694A" : "#8A9894"} fontWeight={win ? 700 : 400}>{won(a.cost)}</text>
                    <rect x={470} y={y(i) - 22} width={200} height={44} rx={12} fill="#fff" stroke={win ? "#0E9F6E" : "#CFD8D5"} strokeWidth={win ? 2 : 1} />
                    <text x={570} y={y(i) + 4} textAnchor="middle" fontSize={12.5} fontWeight={600}>{a.to === "SELLER_RETURN" ? "판매자 복귀" : `주문 ${a.to}`}</text>
                  </g>
                );
              })}
            </svg>
          )}
        </Card>
        <div className="grid content-start gap-4">
          <div className="overflow-x-auto whitespace-nowrap rounded-xl bg-[#0E1A17] p-3 font-mono text-[13px] text-[#D6F5E8]">min Σ c·x  s.t. Σx_out − Σx_in = b, 0 ≤ x ≤ u</div>
          <Card>
            <div className="text-xs text-ink3">총비용 (전체 네트워크 {res?.graph?.nodes.length ?? 0}노드 · {arcs.length}간선)</div>
            <div className="mt-1 flex items-baseline gap-3"><s className="font-mono text-ink3">{res ? won(res.baseline_cost) : "—"}</s><b className="font-mono text-3xl text-brand">{res ? won(res.total_cost) : "—"}</b></div>
            {res && res.matches.length > 0 && <Button className="mt-3" onClick={commit}>매칭 확정 → 지도에서 보기</Button>}
            <div className="mt-1 text-sm text-ink2">{res ? `기존 방식 대비 절감 ${won(res.saving)}원 · 매칭 ${res.matches.length}건 · ${res.status}` : "간선 비용 = 2,500원/회 + 30원/km + 검수·처리비"}</div>
            {res && <div className="mt-1 text-xs text-ink3">같은 반품을 &apos;가장 가까운 순서&apos;로 배정했다면 총비용 {won(res.greedy_cost)}원</div>}
          </Card>
        </div>
      </div>
      <CounterExampleCard />
    </>
  );
}
