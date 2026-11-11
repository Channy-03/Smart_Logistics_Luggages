"use client";
import { useEffect, useState } from "react";
import { animate, motion } from "framer-motion";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, won } from "@/lib/api";
import { Badge, Card, PageHead } from "@/components/ui/primitives";

function Count({ to, suffix = "%", digits = 1 }: { to: number; suffix?: string; digits?: number }) {
  const [v, setV] = useState(0);
  useEffect(() => { const c = animate(0, to, { duration: 1.2, onUpdate: setV }); return () => c.stop(); }, [to]);
  return <>{(v < 0 ? "−" : "") + Math.abs(v).toFixed(digits)}{suffix}</>;
}

const KPI: [string, number, string][] = [["물류비 (반품 1건)", -16.4, "10,559원 → 8,826원"], ["재판매 리드타임", -40.1, "5.6일 → 3.3일"], ["CO₂", -17.2, "0.402 → 0.333kg"], ["직송 매칭률", 74.6, "1,743건 중 1,300건"], ["환불 (직송 건)", -64.3, "5.6일 → 2.0일"], ["이동거리", -25.7, "185 → 138km"]];

// 사전 계산 결과: r_route_sim.py (창원시 30일, 주문 60,000건, 반품 9,015건, 합성 데이터). 발표 중 재실행하지 않는다.
const PER_RETURN = [{ name: "배송비", 기존: 8059, R_ROUTE: 6459 }, { name: "물류비", 기존: 10559, R_ROUTE: 8826 }, { name: "가치 하락", 기존: 1064, R_ROUTE: 945 }];
const SENS: [string, string, string, string][] = [["기본 (SKU 2천, 인기 쏠림)", "74.6%", "−16.4%", "−17.2%"], ["SKU 2만, 수요 분산 (가장 보수적)", "43.3%", "−9.9%", "−9.8%"], ["직송가능 10%", "—", "−8.3%", "−8.8%"], ["직송가능 30%", "—", "−24.7%", "−25.9%"]];

export default function Impact() {
  const [live, setLive] = useState<{ n: number; cost: number; km: number; co2: number }>();
  useEffect(() => { const f = () => api.kpi().then(k => setLive(k.live)).catch(() => undefined); f(); const t = setInterval(f, 5000); return () => clearInterval(t); }, []);

  return (
    <>
      <PageHead eyebrow="Analytics" title="Impact Dashboard" sub="위쪽은 창원시 30일 합성 데이터 시뮬레이션 결과, 아래쪽은 이 서버에서 실제로 처리한 반품의 누적값입니다."
        right={<Badge tone="gray">시뮬레이션 · 사전 계산</Badge>} />
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
        {KPI.map(([l, v, s]) => (
          <Card key={l}><div className="text-xs text-ink3">{l}</div><motion.div className="my-1 font-mono text-4xl font-semibold tracking-tight text-brand"><Count to={v} /></motion.div><div className="text-xs text-ink3">{s}</div></Card>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <b>반품 1건당 비용 (원)</b><div className="text-xs text-ink3">기존 방식 vs R_ROUTE, 시뮬레이션 평균</div>
          <div className="mt-3 h-64">
            <ResponsiveContainer><BarChart data={PER_RETURN} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid horizontal={false} stroke="#E6ECEA" /><XAxis type="number" tickFormatter={v => won(v)} /><YAxis type="category" dataKey="name" width={70} />
              <Tooltip formatter={(v: number) => `${won(v)}원`} /><Legend /><Bar dataKey="기존" fill="#CBD5D2" radius={4} /><Bar dataKey="R_ROUTE" fill="#0E9F6E" radius={4} />
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <b>가정을 바꾸면</b><div className="text-xs text-ink3">가장 불리한 가정까지 공개합니다</div>
          <table className="mt-3 w-full text-[13px]"><thead><tr className="text-left text-xs text-ink3"><th className="py-1.5">시나리오</th><th className="text-right">직송 매칭률</th><th className="text-right">물류비</th><th className="text-right">CO₂</th></tr></thead>
            <tbody>{SENS.map(([a, b, c, d], i) => <tr key={a} className={`border-t border-black/[.06] ${i === 1 ? "font-semibold" : ""}`}><td className="py-1.5">{a}</td><td className="text-right font-mono">{b}</td><td className="text-right font-mono">{c}</td><td className="text-right font-mono">{d}</td></tr>)}</tbody></table>
        </Card>
      </div>
      <Card className="mt-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><b>이 서버에서 실제로 처리한 반품</b><span className="text-xs text-ink3">재판매 완료(배송) 시점에만 더해져요</span></div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["처리 건수", `${live?.n ?? 0}건`], ["절감 물류비", `${won(live?.cost ?? 0)}원`], ["줄인 이동거리", `${Math.round(live?.km ?? 0)}km`], ["줄인 CO₂", `${(live?.co2 ?? 0).toFixed(2)}kg`]].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-black/[.06] bg-white p-3"><div className="text-xs text-ink3">{k}</div><div className="font-mono text-xl">{v}</div></div>
          ))}
        </div>
      </Card>
    </>
  );
}
