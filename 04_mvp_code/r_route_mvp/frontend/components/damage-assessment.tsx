"use client";

import { useState } from "react";
import { api, type DamageAssessment } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui/primitives";

const GRADE_LABEL: Record<DamageAssessment["grade"], string> = {
  S: "새상품", A: "미세 흠집", B: "눈에 띄는 파손", C: "재판매 불가",
};
const TONE: Record<DamageAssessment["grade"], "mint" | "amber" | "gray"> = {
  S: "mint", A: "mint", B: "amber", C: "gray",
};

export function DamageAssessmentUpload() {
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState<DamageAssessment>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function choose(next?: File) {
    if (!next) return;
    setFile(next); setResult(undefined); setError("");
    setPreview(URL.createObjectURL(next));
  }
  async function submit() {
    if (!file) return;
    setBusy(true); setError("");
    try { setResult(await api.assessDamage(file)); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return <Card className="grid max-w-2xl gap-4">
    <div><p className="text-xs font-semibold text-brand">GEMINI VISION</p><h2 className="mt-1 text-xl font-bold">반품 상품 손상 판독</h2>
      <p className="mt-1 text-sm text-ink2">사진 한 장을 올리면 S~C 등급과 이미지에서 확인한 근거를 반환합니다.</p></div>
    <label className="relative grid min-h-52 place-items-center overflow-hidden rounded-2xl border-[1.5px] border-dashed border-black/15 bg-white/60 p-3 text-center text-sm">
      {preview ? <img src={preview} alt="업로드한 반품 상품" className="max-h-60 rounded-lg" /> : <span><b>사진을 눌러 선택하세요</b><br /><span className="text-xs text-ink3">JPEG, PNG, WebP · 최대 10MB</span></span>}
      <input type="file" accept="image/jpeg,image/png,image/webp" className="absolute inset-0 cursor-pointer opacity-0" aria-label="반품 상품 사진" onChange={e => choose(e.target.files?.[0])} />
    </label>
    <div><Button onClick={submit} disabled={!file || busy}>{busy ? "Vision 판독 중…" : "손상 판독하기"}</Button></div>
    {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">판독 오류: {error}</p>}
    {result && <section className="rounded-2xl border border-black/[.08] bg-white p-4">
      <div className="flex items-center gap-2"><Badge tone={TONE[result.grade]}>{result.grade} · {GRADE_LABEL[result.grade]}</Badge><span className="text-xs text-ink3">신뢰도 {Math.round(result.confidence * 100)}%</span></div>
      <p className="mt-3 font-semibold">{result.damage_summary}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink2">{result.visible_evidence.map((item, i) => <li key={i}>{item}</li>)}</ul>
      {result.needs_manual_review && <p className="mt-3 rounded-xl bg-[#FBF5EA] p-2.5 text-sm text-[#795B15]">사진만으로 확정하기 어려워 허브 실물 검수가 필요합니다.</p>}
    </section>}
  </Card>;
}
