"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card } from "@/components/ui/primitives";

const NEW_PATH = "M80 270 C 150 300, 220 300, 280 270 C 340 240, 410 240, 480 270";
const OLD_PATH = "M80 270 C 120 60, 440 40, 480 120";

function FlowHero() {
  return (
    <svg viewBox="0 0 560 380" className="h-auto w-full" role="img" aria-label="반품 고객에서 허브를 거쳐 다음 구매자로 가는 흐름">
      <path d={OLD_PATH} fill="none" stroke="#C9D3D0" strokeWidth={2} strokeDasharray="6 7" />
      <text x={282} y={70} textAnchor="middle" fontSize={12} fill="#8A9894" fontFamily="var(--font-mono)">기존 · 왕복 600km · 5.6일</text>
      <rect x={422} y={70} width={116} height={34} rx={10} fill="#fff" stroke="#DCE3E1" />
      <text x={480} y={92} textAnchor="middle" fontSize={12} fill="#8A9894">수도권 판매자 창고</text>
      <motion.path d={NEW_PATH} fill="none" stroke="#0E9F6E" strokeWidth={3} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.4, ease: "easeInOut" }} />
      <text x={280} y={362} textAnchor="middle" fontSize={12.5} fill="#06694A" fontWeight={600} fontFamily="var(--font-mono)">R_ROUTE · 1.6km · 2.1일</text>
      {[[80, "반품 고객", "상남동"], [280, "상남 허브", "검수 · QR 봉인"], [480, "다음 구매자", "1.0km 거리"]].map(([x, a, b], i) => (
        <g key={a as string} transform={`translate(${x},270)`}>
          {i === 1 ? <rect x={-20} y={-20} width={40} height={40} rx={11} fill="#0B1513" transform="rotate(45)" /> : <circle r={20} fill={i === 2 ? "#0E9F6E" : "#fff"} stroke="#0B1513" strokeWidth={i ? 0 : 1.5} />}
          {i === 1 && <text y={5} textAnchor="middle" fontSize={12} fontWeight={700} fill="#34D399" fontFamily="var(--font-mono)">HUB</text>}
          <text y={44} textAnchor="middle" fontSize={13} fontWeight={600} fill="#0B1513">{a}</text>
          <text y={61} textAnchor="middle" fontSize={11.5} fill="#8A9894">{b}</text>
        </g>
      ))}
      <motion.circle r={7} fill="#0E9F6E" stroke="#fff" strokeWidth={2}
        style={{ offsetPath: `path("${NEW_PATH}")` } as React.CSSProperties}
        animate={{ offsetDistance: ["0%", "100%"] } as never} transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }} />
    </svg>
  );
}

export default function Home() {
  const [live, setLive] = useState<{ n: number; cost: number } | null>(null);
  useEffect(() => { api.kpi().then(k => setLive(k.live)).catch(() => setLive(null)); }, []);
  const stats = [["반품 1건 물류비", "−16.4%", "보수적 −9.9%"], ["재판매 리드타임", "−40%", "5.6일 → 3.3일"], ["CO₂ 배출", "−17.2%", "반품 1건 기준"], ["직송 매칭률", "74.6%", "직송가능 반품 대비"]];
  return (
    <>
      <section className="grid items-center gap-7 py-6 md:grid-cols-[1fr_1.1fr]">
        <div>
          <div className="font-mono text-[11.5px] uppercase tracking-[.14em] text-brand">Reverse logistics, re-routed</div>
          <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-2 text-[clamp(34px,5.2vw,58px)] font-bold leading-[1.08] tracking-tight">
            반품을<br /><span className="text-brand">돌려보내지 않는</span><br />물류
          </motion.h1>
          <p className="mb-6 mt-4 max-w-[46ch] text-[17px] text-ink2">반품 접수 순간 상품을 이동 중 재고(ATP)로 편입하고, 같은 동네의 다음 구매자에게 바로 보냅니다.</p>
          <div className="flex flex-wrap gap-2.5">
            <Link href="/analyze"><Button size="lg">▶ 반품 한 건 따라가기</Button></Link>
            <Link href="/engine"><Button size="lg" variant="ghost">최적화 엔진 보기</Button></Link>
          </div>
          <p className="mt-5 font-mono text-xs text-ink3">반품은 돌아가는 것이 아니라 다시 출발하는 것이다.</p>
        </div>
        <Card className="p-3"><FlowHero /></Card>
      </section>
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map(([l, v, s], i) => (
          <Card key={l}><div className="text-xs text-ink3">{l}</div><div className={`font-mono text-3xl font-semibold tracking-tight ${i < 3 ? "text-brand" : ""}`}>{v}</div><div className="text-xs text-ink3">{s}</div></Card>
        ))}
      </div>
      <p className="mt-4 font-mono text-xs text-ink3">
        {live ? `API 연결됨 · 오늘 처리 ${live.n}건 · 실절감 ${live.cost.toLocaleString("ko-KR")}원` : "API 미연결 · backend에서 uvicorn app.main:app 실행"} · 수치는 창원시 합성 데이터 시뮬레이션
      </p>
    </>
  );
}
