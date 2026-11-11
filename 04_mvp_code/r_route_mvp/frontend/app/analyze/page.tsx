"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, caseStore, pct, won, type Decision, type Prediction } from "@/lib/api";
import { Badge, Button, Card, PageHead } from "@/components/ui/primitives";
import { ModelPanel } from "@/components/model-panel";

const LABEL: Record<string, string> = { direct: "다음 구매자 직송", hub_storage: "허브 보관 후 판매", seller_return: "판매자 창고 복귀", refurbish: "리퍼·리셀", donation: "기부", disposal: "폐기" };
const GOOD = "사이즈가 작아요. 한 번도 신지 않았고 포장 그대로입니다.";
const SAMPLES = [
  { id: "new", label: "새것 사진", file: "new.jpg", reason: "size", memo: GOOD },
  { id: "dark", label: "어둡고 흐린 사진", file: "dark_blurry.jpg", reason: "size", memo: GOOD },
  { id: "damaged", label: "파손 사유", file: "stained.jpg", reason: "damaged", memo: "앞코에 얼룩이 생겼어요" },
  { id: "mismatch", label: "사유·메모 불일치", file: "new.jpg", reason: "size", memo: "사이즈가 작고 앞코에 얼룩이 있어요" },
];
const STEPS = ["사진 품질 확인", "반품 사유 분석", "종합 판단"];
type Hist = { id: string; thumb: string; label: string; grade: string; p: number; photo: number; at: string };

async function toDataURL(url: string) {
  const b = await (await fetch(url)).blob();
  return new Promise<string>(res => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.readAsDataURL(b); });
}
async function thumb(src?: string) {
  if (!src) return "";
  const im = new Image(); im.src = src; await im.decode();
  const c = document.createElement("canvas"); c.width = 96; c.height = Math.round(96 * im.height / im.width);
  c.getContext("2d")!.drawImage(im, 0, 0, c.width, c.height); return c.toDataURL("image/jpeg", .6);
}

function Waterfall({ pred }: { pred: Prediction }) {
  let cur = pred.baseline * 100;
  const rows = pred.contributions.map(c => { const from = cur; cur += c.delta_pp; return { ...c, from, to: cur }; });
  const x = (v: number) => `${Math.max(0, Math.min(100, v))}%`;
  return (
    <div className="space-y-1.5 text-[13px]">
      <div className="grid grid-cols-[120px_1fr_56px] items-center gap-2"><span className="text-ink2">비슷한 반품 평균</span>
        <div className="relative h-5 rounded bg-black/[.04]"><div className="absolute inset-y-0 left-0 rounded bg-[#C9D3D0]" style={{ width: x(pred.baseline * 100) }} /></div>
        <span className="text-right font-mono">{pct(pred.baseline)}</span></div>
      {rows.map(r => {
        const lo = Math.min(r.from, r.to), w = Math.abs(r.to - r.from), up = r.delta_pp >= 0;
        return (
          <div key={r.key}>
            <div className="grid grid-cols-[120px_1fr_56px] items-center gap-2"><span className={r.key === "photo" ? "font-semibold" : ""}>{r.label}</span>
              <div className="relative h-5 rounded bg-black/[.04]">
                <motion.div className={`absolute inset-y-0 rounded ${up ? "bg-brand/80" : "bg-[#D1453B]/70"}`} style={{ left: x(lo) }} initial={{ width: 0 }} animate={{ width: `${Math.max(.6, w)}%` }} transition={{ duration: .5 }} />
              </div>
              <span className={`text-right font-mono ${up ? "text-[#06694A]" : "text-[#B23A31]"}`}>{up ? "+" : "−"}{Math.abs(r.delta_pp).toFixed(1)}%p</span></div>
            {r.note && <div className="ml-[128px] text-xs text-ink3">{r.note}</div>}
          </div>
        );
      })}
      <div className="grid grid-cols-[120px_1fr_56px] items-center gap-2 border-t border-black/[.06] pt-1.5 font-semibold"><span>최종</span>
        <div className="relative h-5 rounded bg-black/[.04]"><div className="absolute inset-y-0 left-0 rounded bg-ink" style={{ width: x(pred.resale_prob * 100) }} /></div>
        <span className="text-right font-mono">{pct(pred.resale_prob)}</span></div>
    </div>
  );
}

export default function Analyze() {
  const router = useRouter();
  const [reason, setReason] = useState("size");
  const [memo, setMemo] = useState(GOOD);
  const [days, setDays] = useState(3);
  const [img, setImg] = useState<string>();
  const [label, setLabel] = useState("직접 업로드");
  const [busy, setBusy] = useState(false);
  const [pred, setPred] = useState<Prediction>();
  const [dec, setDec] = useState<Decision>();
  const [rid, setRid] = useState("");
  const [err, setErr] = useState("");
  const [hist, setHist] = useState<Hist[]>([]);
  const [panel, setPanel] = useState(false);
  useEffect(() => { try { setHist(JSON.parse(caseStore.get("history") || "[]")); } catch { /* ignore */ } }, []);

  async function pick(s: typeof SAMPLES[number]) {
    setReason(s.reason); setMemo(s.memo); setLabel(s.label); setImg(await toDataURL(`/samples/${s.file}`));
  }
  async function run() {
    setBusy(true); setErr(""); setPred(undefined); setDec(undefined);
    try {
      const r = await api.createReturn({ reason_code: reason, reason_text: memo, days_since_purchase: days });
      caseStore.set("rid", r.return_id); setRid(r.return_id);
      const p = await api.analyze(r.return_id, img); setPred(p);
      setDec(await api.decide(r.return_id));
      const h: Hist = { id: r.return_id, thumb: await thumb(img), label: img ? label : "사진 없음", grade: p.grade, p: p.resale_prob,
        photo: p.contributions.find(c => c.key === "photo")?.delta_pp ?? 0, at: new Date().toLocaleTimeString("ko-KR") };
      const next = [h, ...hist].slice(0, 3); setHist(next); caseStore.set("history", JSON.stringify(next));
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  }
  const evs = dec ? Object.entries(dec.expected_values).sort((a, b) => b[1] - a[1]) : [];
  const tone = pred?.grade === "A" ? "mint" : pred?.grade === "B" ? "amber" : "gray";

  return (
    <>
      <PageHead eyebrow="AI Prediction Layer" title="반품 접수와 재판매 가능성 분석" sub="반품 사유, 사진 품질, 구매 정보를 함께 보고 판단합니다. 결과마다 어떤 입력이 얼마나 영향을 줬는지 보여줍니다."
        right={<Badge tone="gray" className="font-mono">{rid || "새 반품"}</Badge>} />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
        <Card className="grid content-start gap-3.5">
          <div className="rounded-2xl border border-black/[.06] bg-white p-3"><b className="text-sm">나이키 에어포스 1 &apos;07 · 270mm</b><div className="text-xs text-ink3">129,000원 · 패션 · 판매자 창고 수도권(300km)</div></div>
          <div>
            <div className="mb-1.5 text-xs text-ink3">샘플로 바로 해보기</div>
            <div className="flex flex-wrap gap-1.5">{SAMPLES.map(s => (
              <button key={s.id} onClick={() => pick(s)} className={`rounded-full border px-3 py-1.5 text-[13px] ${label === s.label ? "border-ink bg-ink text-white" : "border-black/10 bg-white hover:bg-black/[.03]"}`}>{s.label}</button>
            ))}</div>
          </div>
          <label className="text-xs text-ink3">반품 사유
            <select value={reason} onChange={e => setReason(e.target.value)} className="mt-1 w-full rounded-xl border border-black/10 bg-white p-2.5 text-sm text-ink">
              <option value="size">사이즈가 맞지 않아요</option><option value="change_of_mind">단순 변심</option><option value="defect">상품 불량</option><option value="damaged">파손·오염</option>
            </select></label>
          <label className="text-xs text-ink3">구매 후 경과일<input type="number" min={0} max={30} value={days} onChange={e => setDays(+e.target.value)} className="mt-1 w-full rounded-xl border border-black/10 bg-white p-2.5 text-sm text-ink" /></label>
          <label className="text-xs text-ink3">상세 사유<textarea value={memo} onChange={e => setMemo(e.target.value)} className="mt-1 w-full rounded-xl border border-black/10 bg-white p-2.5 text-sm text-ink" /></label>
          <label className="relative grid min-h-36 place-items-center overflow-hidden rounded-2xl border-[1.5px] border-dashed border-black/15 bg-white/60 p-3 text-center text-sm">
            {img ? <img src={img} alt="상품 사진" className="max-h-44 rounded-lg" /> : <span><b>사진을 끌어다 놓거나 눌러서 선택</b><br /><span className="text-xs text-ink3">사진이 없으면 사진 품질은 반영하지 않아요</span></span>}
            <input type="file" accept="image/*" className="absolute inset-0 opacity-0" aria-label="상품 사진" onChange={e => { const f = e.target.files?.[0]; if (!f) return; const r = new FileReader(); r.onload = () => { setImg(String(r.result)); setLabel("직접 업로드"); }; r.readAsDataURL(f); }} />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={run} disabled={busy}>{busy ? "분석 중…" : "AI 분석 실행"}</Button>
            {busy && <span className="text-xs text-ink3">{STEPS.join(" → ")}</span>}
            {img && !busy && <button className="text-xs text-ink3 underline" onClick={() => { setImg(undefined); setLabel("사진 없음"); }}>사진 빼기</button>}
          </div>
          {err && <p className="text-sm text-red-600">API 오류: {err}</p>}
        </Card>

        <Card className="grid content-start gap-4">
          {!pred ? <div className="grid h-72 place-items-center text-center text-ink3">샘플을 고르거나 사진을 올리고<br />AI 분석을 실행하세요</div> : (
            <>
              <div>
                <div className="flex flex-wrap items-center gap-2"><Badge tone={tone}>{pred.grade} · {pred.grade_label}</Badge><span className="font-mono text-xs text-ink3">{pred.model_version}</span></div>
                <h2 className="mt-2 text-xl font-bold leading-snug">{pred.verdict}</h2>
                <p className="mt-1 text-sm text-ink2">재판매 가능성 <b className="font-mono text-ink">{pct(pred.resale_prob)}</b> · 비슷한 반품 평균 {pct(pred.baseline)}</p>
              </div>
              {pred.mismatch.length > 0 && (
                <div className="rounded-xl border border-[#F0D9A8] bg-[#FBF5EA] p-3 text-sm"><b>사유와 상세 사유가 맞지 않아요.</b> 상세 사유에서 &apos;{pred.mismatch.join("', '")}&apos;을(를) 찾았어요. 직송하지 않고 허브에서 실물을 확인해요.</div>
              )}
              <div>
                <div className="mb-2 text-xs font-semibold text-ink2">이 값이 나온 이유</div>
                <Waterfall pred={pred} />
                {pred.photo && <div className="mt-2 flex flex-wrap gap-1.5 text-xs">{[["선명도", pred.photo.sharpness], ["밝기", pred.photo.brightness], ["대비", pred.photo.contrast]].map(([k, v]) => (
                  <span key={k as string} className="rounded-full bg-black/[.05] px-2 py-0.5">{k} <b className="font-mono">{Number(v).toFixed(2)}</b></span>))}
                  <span className="text-ink3">사진 품질만 봐요. 얼룩·찢김은 허브 검수에서 확인해요.</span></div>}
              </div>
              {hist.length > 1 && (
                <div>
                  <div className="mb-2 text-xs font-semibold text-ink2">이전 분석과 비교</div>
                  <div className="grid grid-cols-3 gap-2">{hist.map((h, i) => (
                    <div key={h.id} className={`rounded-xl border p-2 text-xs ${i === 0 ? "border-ink" : "border-black/[.06]"}`}>
                      {h.thumb ? <img src={h.thumb} alt="" className="mb-1 h-12 w-full rounded object-cover" /> : <div className="mb-1 grid h-12 place-items-center rounded bg-black/[.04] text-ink3">사진 없음</div>}
                      <div className="truncate">{i === 0 ? "지금" : h.at} · {h.label}</div>
                      <div className="font-mono"><b>{h.grade}</b> {pct(h.p)} · 사진 {h.photo >= 0 ? "+" : "−"}{Math.abs(h.photo).toFixed(1)}%p</div>
                    </div>))}</div>
                </div>
              )}
              {dec && (
                <details className="rounded-xl border border-black/[.06] bg-white p-3 text-[13px]">
                  <summary className="cursor-pointer font-semibold">처리 경로: {LABEL[dec.path]} <span className="font-normal text-ink3">· {dec.reason}</span></summary>
                  <div className="mt-2 space-y-1">{evs.map(([k, v]) => (
                    <div key={k} className={`flex justify-between ${k === dec.path ? "font-semibold" : "text-ink2"}`}><span>{LABEL[k]}</span><span className="font-mono">{won(v)}원</span></div>))}
                    {dec.blocked.length > 0 && <div className="text-xs text-ink3">선택지에서 뺀 경로: {dec.blocked.map(b => LABEL[b]).join(", ")}</div>}
                    <div className="text-xs text-ink3">기대 순가치 = 회수 가치 − 운송비 − 검수비 − 가치 하락 − 탄소 비용 + 신규 출고 절감분</div></div>
                </details>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3 text-xs text-ink3">
                  <span className="rounded-full bg-black/[.05] px-2 py-0.5">데모 모드</span>
                  <button className="underline" onClick={() => setPanel(true)}>이 분석은 어떻게 만들어지나요?</button>
                </div>
                {dec && ["direct", "hub_storage"].includes(dec.path) && <Button onClick={() => router.push("/engine")}>최적 구매자 찾기 →</Button>}
              </div>
              <p className="-mt-2 text-xs text-ink3">최종 판정은 허브 실물 검수에서 확정돼요.</p>
            </>
          )}
        </Card>
      </div>
      <ModelPanel open={panel} onClose={() => setPanel(false)} />
    </>
  );
}
