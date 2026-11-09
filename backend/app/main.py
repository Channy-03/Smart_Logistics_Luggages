"""R_ROUTE MVP API (FastAPI)

실행:  uvicorn app.main:app --reload --port 8000    (backend 폴더에서)
문서:  http://localhost:8000/docs
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import conn, dumps, now, one, rows
from .engine import costs as C
from .engine.decision import decide
from .engine.mcf import greedy, solve
from .ml.predictor import MODEL_CARD, get_predictor
from .seed import nearest_hub, road_km, seed
from .verify import append_event, read_token, sign_token, verify_chain

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    seed(reset=True)
    get_predictor()
    yield


app = FastAPI(lifespan=lifespan, title="R_ROUTE API", version="0.2.0",
              description="반품 접수 순간 이동 중 재고(ATP)로 편입해 지역 신규 주문에 재할당하는 역물류 엔진")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 시뮬레이션(창원시 30일, 합성 데이터) 기준선 KPI
SIM_BASELINE = {"cost_cut_pct": 16.4, "resale_lead_cut_pct": 40.1, "co2_cut_pct": 17.2, "match_rate_pct": 74.6,
                "km_cut_pct": 25.7, "refund_days": {"before": 5.6, "after_direct": 2.0}}




# ---------- schemas ----------
class ReturnIn(BaseModel):
    order_ref: str = "OD-2610427"
    sku: str = "SKU-AF270"
    customer_name: str = "김*진"
    lat: float = 35.2195
    lng: float = 128.6850
    reason_code: str = Field("size", pattern="^(size|change_of_mind|late|wrong_item|defect|damaged)$")
    reason_text: str | None = "사이즈가 작아요. 한 번도 신지 않았고 포장 그대로입니다."
    days_since_purchase: int = 3
    prior_returns: int = 0


class AnalyzeIn(BaseModel):
    image_base64: str | None = None


class InspectionIn(BaseModel):
    return_id: str
    hub_id: str | None = None
    checklist: dict = {"exterior": True, "components": True, "weight": True, "tag": True}
    grade: str | None = None


class SimIn(BaseModel):
    direct_ratio: float = Field(.2, ge=.05, le=.6)
    hold_hours: int = Field(72, ge=12, le=168)
    orders_per_day: int = Field(2000, ge=500, le=6000)
    days: int = Field(10, ge=7, le=30)  # 반품은 주문 후 4일+ 뒤 발생하므로 7일 미만은 워밍업 구간


# ---------- helpers ----------
def _product(c, sku):
    p = one(c, "SELECT * FROM products WHERE sku=?", (sku,))
    if not p:
        raise HTTPException(404, f"unknown sku {sku}")
    return p


def _return(c, rid):
    r = one(c, "SELECT * FROM returns WHERE return_id=?", (rid,))
    if not r:
        raise HTTPException(404, f"unknown return {rid}")
    return r


# ---------- endpoints ----------
@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL_CARD, "metrics": get_predictor().metrics}


@app.get("/api/model")
def model_info():
    """모델 정보 패널용: 입력, 학습 데이터, 검증 성능, 알려진 한계, 파일럿 계획"""
    return MODEL_CARD | {"metrics": get_predictor().metrics,
                         "grade_rule": {"A": ">= 80%", "B": "60~80%", "C": "< 60%", "direct_threshold": "75%"}}


@app.post("/api/demo/reset")
def demo_reset():
    seed(reset=True)
    return {"ok": True}


@app.post("/api/returns", status_code=201)
def create_return(body: ReturnIn):
    rid = f"RT-{datetime.now():%y%m}-{uuid.uuid4().hex[:4].upper()}"
    with conn() as c:
        _product(c, body.sku)
        hub = nearest_hub(c, body.lat, body.lng)
        c.execute("INSERT INTO returns (return_id, order_ref, sku, customer_name, lat, lng, reason_code, reason_text,"
                  " days_since_purchase, prior_returns, created_at, nearest_hub) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, body.order_ref, body.sku, body.customer_name, body.lat, body.lng, body.reason_code,
                   body.reason_text, body.days_since_purchase, body.prior_returns, now(), hub["hub_id"]))
        append_event(c, rid, "REQUESTED", {"reason": body.reason_code, "sku": body.sku})
    return {"return_id": rid, "nearest_hub": hub}


@app.post("/api/returns/{rid}/analyze")
def analyze(rid: str, body: AnalyzeIn):
    img = base64.b64decode(body.image_base64.split(",")[-1]) if body.image_base64 else None
    with conn() as c:
        r = _return(c, rid)
        p = _product(c, r["sku"])
        pred = get_predictor().predict(r["reason_code"], r["reason_text"], p["category"], p["price"],
                                       r["days_since_purchase"], r["prior_returns"], img)
        c.execute("INSERT OR REPLACE INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (rid, pred.resale_prob, pred.grade, pred.verdict, pred.baseline, dumps(pred.contributions),
                   dumps(pred.mismatch), dumps(pred.photo) if pred.photo else None, pred.model_version, now()))
        c.execute("UPDATE returns SET status='analyzed' WHERE return_id=?", (rid,))
        append_event(c, rid, "AI_GRADED", {"p": pred.resale_prob, "grade": pred.grade, "mismatch": pred.mismatch})
    return pred.__dict__ | {"product": p}


@app.post("/api/returns/{rid}/decide")
def decide_path(rid: str, hold_hours: int = 72):
    with conn() as c:
        r = _return(c, rid)
        p = _product(c, r["sku"])
        pred = one(c, "SELECT * FROM predictions WHERE return_id=?", (rid,))
        if not pred:
            raise HTTPException(409, "analyze first")
        hub = one(c, "SELECT * FROM hubs WHERE hub_id=?", (r["nearest_hub"],))
        km_ch = road_km(r["lat"], r["lng"], hub["lat"], hub["lng"])
        open_o = rows(c, "SELECT * FROM orders WHERE sku=? AND status='open' AND accepts_inspected_return=1", (r["sku"],))
        nearest = min((road_km(hub["lat"], hub["lng"], o["lat"], o["lng"]) for o in open_o), default=None)
        d = decide(pred["resale_prob"], p["price"], p["category"], bool(p["restricted"]), p["seller_km"], km_ch,
                   nearest, len(open_o), hold_hours, mismatch=bool(json.loads(pred["mismatch"] or "[]")))
        c.execute("INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?)", (rid, d["path"], dumps(d["expected_values"]), d["reason"], now()))
        if d["path"] in ("direct", "hub_storage"):
            t = datetime.now(timezone.utc)
            c.execute("INSERT OR REPLACE INTO atp_inventory VALUES (?,?,?,?,?,?,?)",
                      (rid, r["sku"], hub["hub_id"], pred["resale_prob"], (t + timedelta(hours=18)).isoformat(timespec="seconds"),
                       (t + timedelta(hours=18 + hold_hours)).isoformat(timespec="seconds"), "in_transit"))
            c.execute("UPDATE returns SET status='atp' WHERE return_id=?", (rid,))
            append_event(c, rid, "ATP_ENROLLED", {"hub": hub["hub_id"], "promise_qty": pred["resale_prob"]})
        else:
            c.execute("UPDATE returns SET status=? WHERE return_id=?",
                      ({"seller_return": "returned_to_seller", "refurbish": "refurbish", "donation": "donated",
                        "disposal": "disposed"}[d["path"]], rid))
    return d | {"hub": hub, "km_customer_hub": round(km_ch, 2), "candidate_orders": len(open_o)}


@app.post("/api/match/run")
def match_run(explain: bool = False, commit: bool = True):
    run_id = f"RUN-{uuid.uuid4().hex[:6]}"
    with conn() as c:
        pool = rows(c, "SELECT a.return_id, a.sku, a.hub_id FROM atp_inventory a WHERE a.state IN ('in_transit','at_hub')")
        orders = rows(c, "SELECT * FROM orders WHERE status='open'")
        hubs = {h["hub_id"]: h for h in rows(c, "SELECT * FROM hubs")}
        products = {p["sku"]: p for p in rows(c, "SELECT * FROM products")}
        res = solve(pool, orders, hubs, products, explain=explain)
        if commit:
            for m in res["matches"]:
                r = _return(c, m["return_id"])
                hub = hubs[m["hub_id"]]
                km_ch = road_km(r["lat"], r["lng"], hub["lat"], hub["lng"])
                c.execute("INSERT INTO matches VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (f"MT-{uuid.uuid4().hex[:6]}", m["return_id"], m["order_id"], m["hub_id"], km_ch, m["km_hub_buyer"],
                           m["km_saved"], m["cost_saved"], m["co2_saved"], run_id, now()))
                c.execute("UPDATE atp_inventory SET state='allocated' WHERE return_id=?", (m["return_id"],))
                c.execute("UPDATE orders SET status='matched', fulfilled_by=? WHERE order_id=?", (m["return_id"], m["order_id"]))
                c.execute("UPDATE returns SET status='matched' WHERE return_id=?", (m["return_id"],))
                append_event(c, m["return_id"], "MATCHED", {"order": m["order_id"], "km": m["km_hub_buyer"], "run": run_id})
    return res | {"run_id": run_id}


# 반례: '가장 가까운 순서' 배정보다 최소비용 흐름이 나은 경우 (DB를 바꾸지 않는 독립 시나리오)
# 반품 A(상남)가 먼저 들어와 가장 가까운 주문 P를 가져가면, 반품 B(내서)는 반경 25km 안에 남은 주문이 없어
# 수도권 판매자 창고로 돌아가고 주문 Q는 수도권 신규 재고로 출고된다. 최소비용 흐름은 A→Q, B→P로 둘 다 살린다.
CX_HUBS = {"H04": {"hub_id": "H04", "name": "상남 허브", "lat": 35.2212, "lng": 128.6808},
           "H07": {"hub_id": "H07", "name": "내서 허브", "lat": 35.2540, "lng": 128.5150}}
CX_RETURNS = [{"return_id": "RT-CX-A", "sku": "SKU-HD-M", "hub_id": "H04", "arrived": "14:02"},
              {"return_id": "RT-CX-B", "sku": "SKU-HD-M", "hub_id": "H07", "arrived": "14:05"}]
CX_ORDERS = [{"order_id": "OD-CX-P", "sku": "SKU-HD-M", "lat": 35.2350, "lng": 128.6600, "accepts_inspected_return": 1, "buyer_name": "한*결"},
             {"order_id": "OD-CX-Q", "sku": "SKU-HD-M", "lat": 35.1600, "lng": 128.7000, "accepts_inspected_return": 1, "buyer_name": "서*연"}]


def _plan_summary(pairs, products):
    """배정 결과의 총 이동거리: 재할당 배송 + 판매자 복귀 + 신규 재고 출고까지 포함"""
    seller_km = products["SKU-HD-M"]["seller_km"]
    used_r = {p["return_id"] for p in pairs}
    used_o = {p["order_id"] for p in pairs}
    legs = [{"from": p["return_id"], "to": p["order_id"], "km": p["km"], "kind": "reallocate"} for p in pairs]
    legs += [{"from": r["return_id"], "to": "SELLER", "km": seller_km, "kind": "seller_return"} for r in CX_RETURNS if r["return_id"] not in used_r]
    legs += [{"from": "NEW_STOCK", "to": o["order_id"], "km": seller_km, "kind": "new_stock"} for o in CX_ORDERS if o["order_id"] not in used_o]
    return legs, round(sum(l["km"] for l in legs), 1)


@app.get("/api/scenario/counterexample")
def counterexample():
    with conn() as c:
        products = {p["sku"]: p for p in rows(c, "SELECT * FROM products")}
    opt = solve(CX_RETURNS, CX_ORDERS, CX_HUBS, products)
    g = greedy(CX_RETURNS, CX_ORDERS, CX_HUBS, products)
    opt_pairs = [{"return_id": m["return_id"], "order_id": m["order_id"], "km": m["km_hub_buyer"]} for m in opt["matches"]]
    g_legs, g_km = _plan_summary(g["pairs"], products)
    o_legs, o_km = _plan_summary(opt_pairs, products)
    km = {f'{r["return_id"]}->{o["order_id"]}': round(road_km(CX_HUBS[r["hub_id"]]["lat"], CX_HUBS[r["hub_id"]]["lng"], o["lat"], o["lng"]), 1)
          for r in CX_RETURNS for o in CX_ORDERS}
    return {"hubs": list(CX_HUBS.values()), "returns": CX_RETURNS, "orders": CX_ORDERS, "distances_km": km,
            "radius_km": C.MATCH_RADIUS_KM,
            "nearest_first": {"pairs": g["pairs"], "legs": g_legs, "total_cost": g["total_cost"], "km": g_km},
            "min_cost_flow": {"pairs": opt_pairs, "legs": o_legs, "total_cost": opt["total_cost"], "km": o_km},
            "explanation": "반품이 들어온 순서대로 가장 가까운 주문을 고르면, 먼저 온 반품 A가 주문 P를 가져갑니다. "
                           "그러면 반품 B는 반경 25km 안에 남은 주문이 없어 수도권 창고로 돌아가고, 주문 Q는 수도권에서 새 재고가 내려옵니다. "
                           "최소비용 흐름은 두 반품을 한꺼번에 보고 A를 Q로, B를 P로 보냅니다."}


@app.get("/api/network")
def network():
    with conn() as c:
        return {
            "hubs": rows(c, "SELECT * FROM hubs"),
            "returns": rows(c, "SELECT r.return_id, r.sku, r.lat, r.lng, r.status, r.nearest_hub, p.name FROM returns r"
                               " JOIN products p USING(sku)"),
            "orders": rows(c, "SELECT o.order_id, o.sku, o.lat, o.lng, o.status, o.buyer_name, p.name FROM orders o"
                              " JOIN products p USING(sku)"),
            "matches": rows(c, "SELECT * FROM matches ORDER BY created_at DESC"),
        }


@app.post("/api/inspections", status_code=201)
def inspect(body: InspectionIn):
    with conn() as c:
        r = _return(c, body.return_id)
        m = one(c, "SELECT * FROM matches WHERE return_id=? ORDER BY created_at DESC LIMIT 1", (body.return_id,))
        hub_id = body.hub_id or (m["hub_id"] if m else r["nearest_hub"])
        passed = sum(bool(v) for v in body.checklist.values())
        pred = one(c, "SELECT grade FROM predictions WHERE return_id=?", (body.return_id,))
        grade = body.grade or ("A" if passed == len(body.checklist) and pred and pred["grade"] == "A"
                               else "B" if passed >= len(body.checklist) - 1 else "C")
        iid = f"IN-{uuid.uuid4().hex[:6]}"
        token = sign_token({"rid": body.return_id, "iid": iid, "hub": hub_id, "grade": grade, "ts": now()})
        c.execute("INSERT INTO inspections VALUES (?,?,?,?,?,?,?)", (iid, body.return_id, hub_id, dumps(body.checklist), grade, token, now()))
        append_event(c, body.return_id, "INSPECTED", {"hub": hub_id, "grade": grade, "checklist": body.checklist})
        append_event(c, body.return_id, "SEALED", {"qr": token[-12:]})
        # 허브 검수 완료 = 판매자 반환 간주(대리수령 약정) -> 즉시 환불
        append_event(c, body.return_id, "REFUNDED", {"basis": "hub_inspection_as_receipt"})
        status = "refunded" if grade in ("A", "B") else "returned_to_seller"
        c.execute("UPDATE returns SET status=? WHERE return_id=?", (status, body.return_id))
        if grade == "C" and m:  # 등급 미달: 매칭 해제, 주문은 신규 재고로
            c.execute("UPDATE orders SET status='open', fulfilled_by=NULL WHERE order_id=?", (m["order_id"],))
    return {"inspection_id": iid, "grade": grade, "qr_token": token, "verify_url": f"/verify/{token}"}


@app.post("/api/returns/{rid}/deliver")
def deliver(rid: str):
    with conn() as c:
        m = one(c, "SELECT * FROM matches WHERE return_id=? ORDER BY created_at DESC LIMIT 1", (rid,))
        if not m:
            raise HTTPException(409, "not matched")
        c.execute("UPDATE returns SET status='resold' WHERE return_id=?", (rid,))
        c.execute("UPDATE orders SET status='fulfilled_return' WHERE order_id=?", (m["order_id"],))
        append_event(c, rid, "DELIVERED", {"order": m["order_id"]})
        c.execute("INSERT INTO kpi_events (return_id, cost_saved, km_saved, co2_saved, refund_days_saved, resale_days_saved, created_at)"
                  " VALUES (?,?,?,?,?,?,?)", (rid, m["cost_saved"], m["km_saved"], m["co2_saved"],
                                              SIM_BASELINE["refund_days"]["before"] - 2.0, 5.6 - 2.1, now()))
    return {"ok": True, "match": m}


@app.get("/api/verify/{token}")
def verify(token: str):
    claims = read_token(token)
    if not claims:
        raise HTTPException(400, "invalid or tampered QR")
    with conn() as c:
        ok, ev = verify_chain(c, claims["rid"])
        r = _return(c, claims["rid"])
        p = _product(c, r["sku"])
    return {"valid": ok, "claims": claims, "product": p["name"],
            "events": [{"type": e["event_type"], "at": e["created_at"], "hash": e["hash"][:12]} for e in ev]}


@app.get("/api/kpi")
def kpi():
    with conn() as c:
        live = one(c, "SELECT COUNT(*) n, COALESCE(SUM(cost_saved),0) cost, COALESCE(SUM(km_saved),0) km,"
                      " COALESCE(SUM(co2_saved),0) co2 FROM kpi_events")
        m = one(c, "SELECT COUNT(*) n FROM matches")
    return {"simulation": SIM_BASELINE, "live": live | {"matches": m["n"]}}


@app.post("/api/simulate")
def simulate(body: SimIn):
    from .sim.r_route_sim import kpis, simulate as run
    P, W, O, R, B, X = run(direct_ratio=body.direct_ratio, hold_hours=body.hold_hours,
                           orders_per_day=body.orders_per_day, days=body.days)
    K = kpis(R, B, X, P)
    out = {k: {"baseline": round(float(v["기존 방식"]), 3), "rroute": round(float(v["R_ROUTE"]), 3)} for k, v in K.iterrows()}
    return {"params": body.model_dump(), "n_orders": len(O), "n_returns": len(R), "kpi": out}
