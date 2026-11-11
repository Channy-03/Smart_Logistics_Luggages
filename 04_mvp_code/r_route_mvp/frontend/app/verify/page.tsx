"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { QRCodeSVG } from "qrcode.react";
import { api, useCaseId, caseStore } from "@/lib/api";
import { Badge, Button, Card, PageHead } from "@/components/ui/primitives";

const ITEMS = [["exterior", "외관 손상·오염 없음"], ["components", "구성품 일치 (박스, 끈, 택)"], ["weight", "무게 오차 ±2% 이내"], ["tag", "정품 태그·시리얼 대조"]] as const;

export default function Verify() {
  const [check, setCheck] = useState<Record<string, boolean>>({ exterior: true, components: true, weight: true, tag: true });
  const [res, setRes] = useState<{ grade: string; qr_token: string }>();
  const [chain, setChain] = useState<{ valid: boolean; events: { type: string; at: string; hash: string }[] }>();
  const [err, setErr] = useState("");
  const rid = useCaseId();

  async function seal() {
    setErr("");
    try {
      const r = await api.inspect(rid, check); setRes(r); caseStore.set("qr", r.qr_token);
      if (r.grade !== "C") await api.deliver(rid).catch(() => undefined);
      setChain(await api.verify(r.qr_token));
    } catch (e) { setErr(String(e)); }
  }
  const url = res ? `${typeof window !== "undefined" ? window.location.origin : ""}/api/verify/${res.qr_token}` : "";

  return (
    <>
      <PageHead eyebrow="Step 7–8 · Verification Hub" title="허브 검수와 QR 인증" sub="허브 검수 완료를 판매자 수령으로 간주(대리수령 약정)해 즉시 환불하고, 다음 구매자는 QR로 이력을 확인합니다."
        right={<Badge tone="gray" className="font-mono">{rid || "반품 없음 · AI 분석부터"}</Badge>} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="grid content-start gap-2.5">
          {ITEMS.map(([k, l]) => (
            <label key={k} className={`flex cursor-pointer items-center gap-3 rounded-xl border bg-white p-3 text-sm ${check[k] ? "border-[#BFEBD8]" : "border-black/[.06]"}`}>
              <input type="checkbox" checked={check[k]} onChange={e => setCheck({ ...check, [k]: e.target.checked })} className="h-5 w-5 accent-[#0E9F6E]" />{l}
            </label>
          ))}
          <Button onClick={seal} disabled={!rid} className="mt-2">검수 완료 · QR 봉인</Button>
          {err && <p className="text-sm text-red-600">{err}</p>}
        </Card>
        <Card className="grid place-items-center gap-3">
          <div className="flex gap-2">{["A", "B", "C"].map(g => (
            <motion.div key={g} animate={{ y: res?.grade === g ? -3 : 0 }} className={`w-20 rounded-2xl border p-3 text-center ${res?.grade === g ? "border-ink bg-ink text-white" : "border-black/[.06] bg-white"}`}>
              <b className="block font-mono text-2xl">{g}</b><span className="text-xs">{{ A: "Like New", B: "Good", C: "Review" }[g]}</span></motion.div>))}</div>
          <div className={`rounded-2xl border border-black/[.06] bg-white p-4 transition ${res ? "" : "opacity-20 blur-[2px]"}`}><QRCodeSVG value={url || "pending"} size={176} /></div>
          <span className="max-w-full truncate font-mono text-[11px] text-ink3">{res ? res.qr_token.slice(0, 24) + "…" : "서명 대기"}</span>
          {res && res.grade !== "C" && <Badge>환불 완료 · 허브 검수 = 반환 간주</Badge>}
        </Card>
        <Card>
          <div className="mb-2 text-xs text-ink3">검수 이력 체인 {chain && (chain.valid ? "· 무결성 확인 ✓" : "· 위변조 감지")}</div>
          {chain?.events.map((e, i) => (
            <motion.div key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * .08 }} className="grid grid-cols-[14px_1fr_auto] items-start gap-2.5 py-1.5 text-[13px]">
              <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-brand" /><b>{e.type}</b><span className="font-mono text-[11px] text-ink3">{e.hash}</span>
            </motion.div>
          )) ?? <p className="text-sm text-ink3">봉인하면 SHA-256 해시 체인이 표시됩니다.</p>}
        </Card>
      </div>
    </>
  );
}
