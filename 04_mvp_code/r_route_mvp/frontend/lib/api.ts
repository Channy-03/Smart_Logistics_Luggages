import { useEffect, useState } from "react";
// FastAPI 백엔드 클라이언트. next.config.mjs가 /api/* 를 RROUTE_API(기본 :8000)로 프록시한다.
export type Contribution = { key: string; label: string; delta_pp: number; note?: string };
export type Prediction = {
  resale_prob: number; grade: "A" | "B" | "C"; grade_label: string; verdict: string; baseline: number;
  contributions: Contribution[]; mismatch: string[];
  photo: { score: number; sharpness: number; brightness: number; contrast: number } | null;
  text_score: number; model_version: string;
};
export type DamageAssessment = {
  grade: "S" | "A" | "B" | "C";
  damage_summary: string;
  visible_evidence: string[];
  confidence: number;
  needs_manual_review: boolean;
  provider: string;
};
export type Decision = {
  path: string; label: string; expected_values: Record<string, number>; blocked: string[]; reason: string;
  hub: Hub; km_customer_hub: number; candidate_orders: number;
};
export type Hub = { hub_id: string; name: string; hub_type: string; lat: number; lng: number };
export type Match = { return_id: string; order_id: string; hub_id: string; km_hub_buyer: number; cost_saved: number; km_saved: number; co2_saved: number };
export type Arc = { from: string; to: string; cost: number; flow: number; kind: string };
export type MatchRun = {
  status: string; run_id: string; total_cost: number; baseline_cost: number; saving: number; matches: Match[];
  greedy_cost: number; graph?: { nodes: { id: string; type: string }[]; arcs: Arc[] };
};
export type Network = {
  hubs: Hub[];
  returns: { return_id: string; sku: string; lat: number; lng: number; status: string; name: string; nearest_hub: string }[];
  orders: { order_id: string; sku: string; lat: number; lng: number; status: string; name: string; buyer_name: string }[];
  matches: (Match & { km_customer_hub: number; created_at: string })[];
};
export type ModelInfo = {
  version: string; inputs: string[]; fusion: string; training_data: string; limitations: string[]; pilot_plan: string;
  metrics: { auc: number; brier: number; n_train: number; n_valid: number; trained_at: string };
  grade_rule: Record<string, string>;
};
type Pair = { return_id: string; order_id: string; km: number };
type Leg = { from: string; to: string; km: number; kind: "reallocate" | "seller_return" | "new_stock" };
export type Plan = { pairs: Pair[]; legs: Leg[]; total_cost: number; km: number };
export type CounterExample = {
  hubs: Hub[]; returns: { return_id: string; hub_id: string; arrived: string }[];
  orders: { order_id: string; lat: number; lng: number; buyer_name: string }[];
  distances_km: Record<string, number>;
  nearest_first: Plan; min_cost_flow: Plan; radius_km: number;
  explanation: string;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { "content-type": "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
const post = <T,>(p: string, body: unknown = {}) => call<T>(p, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => call<{ ok: boolean; metrics: { auc: number; brier: number } }>("/api/health"),
  model: () => call<ModelInfo>("/api/model"),
  reset: () => post("/api/demo/reset"),
  createReturn: (b: Record<string, unknown>) => post<{ return_id: string; nearest_hub: Hub }>("/api/returns", b),
  analyze: (id: string, image_base64?: string) => post<Prediction>(`/api/returns/${id}/analyze`, { image_base64 }),
  assessDamage: async (image: File): Promise<DamageAssessment> => {
    const form = new FormData();
    form.append("image", image);
    const r = await fetch("/api/vision/damage-assessment", { method: "POST", body: form });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },
  decide: (id: string) => post<Decision>(`/api/returns/${id}/decide`),
  runMatch: (explain = false, commit = true) => post<MatchRun>(`/api/match/run?explain=${explain}&commit=${commit}`),
  counterexample: () => call<CounterExample>("/api/scenario/counterexample"),
  network: () => call<Network>("/api/network"),
  inspect: (return_id: string, checklist: Record<string, boolean>) =>
    post<{ grade: string; qr_token: string; inspection_id: string }>("/api/inspections", { return_id, checklist }),
  verify: (token: string) => call<{ valid: boolean; product: string; claims: Record<string, string>; events: { type: string; at: string; hash: string }[] }>(`/api/verify/${token}`),
  deliver: (id: string) => post(`/api/returns/${id}/deliver`),
  kpi: () => call<{ simulation: Record<string, number>; live: { n: number; cost: number; km: number; co2: number; matches: number } }>("/api/kpi"),
};

// 데모 케이스(현재 반품 ID, QR 토큰, 최근 분석 기록)를 화면 간에 공유
type Key = "rid" | "qr" | "history";
export const caseStore = {
  get: (k: Key) => { try { return localStorage.getItem(`rroute.${k}`) || ""; } catch { return ""; } },
  set: (k: Key, v: string) => { try { localStorage.setItem(`rroute.${k}`, v); } catch { /* ignore */ } },
  clear: () => { try { ["rid", "qr", "history"].forEach(k => localStorage.removeItem(`rroute.${k}`)); } catch { /* ignore */ } },
};
export const won = (n: number) => Math.round(n).toLocaleString("ko-KR");
export const pct = (p: number) => `${Math.round(p * 100)}%`;

// 하이드레이션 이후에 로컬 저장소의 케이스 ID를 읽는다 (SSR 정적 HTML과 불일치 방지)
export function useCaseId() {
  const [rid, setRid] = useState("");
  useEffect(() => { setRid(caseStore.get("rid")); }, []);
  return rid;
}
