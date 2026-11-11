"use client";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type ModelInfo } from "@/lib/api";

// "이 분석은 어떻게 만들어지나요?" 사이드 패널. 값은 /api/model 에서 그대로 읽는다.
export function ModelPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [m, setM] = useState<ModelInfo>();
  const [err, setErr] = useState("");
  useEffect(() => { if (open && !m) api.model().then(setM).catch(e => setErr(String(e))); }, [open, m]);
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 z-[60] bg-black/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside role="dialog" aria-label="모델 정보" className="fixed inset-y-0 right-0 z-[61] w-full max-w-md overflow-y-auto bg-white p-6 shadow-2xl"
            initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }}>
            <div className="flex items-start justify-between gap-3">
              <div><div className="font-mono text-[11px] uppercase tracking-[.14em] text-brand">Model card</div><h2 className="text-xl font-bold">이 분석은 어떻게 만들어지나요?</h2></div>
              <button onClick={onClose} className="rounded-full px-3 py-1 text-sm text-ink2 hover:bg-black/5">닫기</button>
            </div>
            {err && <p className="mt-4 text-sm text-red-600">모델 정보를 불러오지 못했어요: {err}</p>}
            {m && (
              <div className="mt-5 space-y-5 text-sm leading-relaxed">
                <section>
                  <h3 className="mb-1 font-semibold">무엇을 보나요</h3>
                  <ul className="list-disc space-y-0.5 pl-5">{m.inputs.map(i => <li key={i}>{i}</li>)}</ul>
                  <p className="mt-1 text-ink2">세 입력을 {m.fusion}으로 합쳐 재판매 가능성을 계산해요.</p>
                </section>
                <section>
                  <h3 className="mb-1 font-semibold">무엇으로 학습했나요</h3>
                  <p className="text-ink2">{m.training_data}</p>
                </section>
                <section className="grid grid-cols-3 gap-2">
                  {[["학습", `${m.metrics.n_train.toLocaleString()}건`], ["검증 AUC", m.metrics.auc.toFixed(2)], ["Brier", m.metrics.brier.toFixed(2)]].map(([k, v]) => (
                    <div key={k} className="rounded-xl border border-black/[.06] p-3"><div className="text-[11px] text-ink3">{k}</div><div className="font-mono text-lg">{v}</div></div>
                  ))}
                </section>
                <p className="-mt-3 text-xs text-ink3">AUC는 정확도가 아니라 &quot;재판매 가능한 반품을 더 높게 줄 세우는 능력&quot;이에요(0.5는 무작위, 1.0은 완벽). 검증 {m.metrics.n_valid.toLocaleString()}건, 학습 시각 {m.metrics.trained_at.slice(0, 16).replace("T", " ")} UTC.</p>
                <section>
                  <h3 className="mb-1 font-semibold">등급 기준</h3>
                  <p className="text-ink2">A {m.grade_rule.A} · B {m.grade_rule.B} · C {m.grade_rule.C}. 직송은 {m.grade_rule.direct_threshold} 이상이고 반품 사유와 상세 사유가 맞을 때만 해요.</p>
                </section>
                <section className="rounded-xl bg-[#FBF5EA] p-3">
                  <h3 className="mb-1 font-semibold">알려진 한계</h3>
                  <ul className="list-disc space-y-1 pl-5 text-ink2">{m.limitations.map(l => <li key={l}>{l}</li>)}</ul>
                </section>
                <section>
                  <h3 className="mb-1 font-semibold">앞으로 어떻게 좋아지나요</h3>
                  <p className="text-ink2">{m.pilot_plan}</p>
                </section>
                <p className="border-t border-black/[.06] pt-3 text-xs text-ink3">AI의 판단은 1차 판단이에요. 다음 구매자에게 가기 전에 허브에서 사람이 직접 확인하고, 기준에 못 미치면 구매자에게는 새 상품이 발송돼요. · 모델 {m.version}</p>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
