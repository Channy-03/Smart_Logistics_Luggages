"""데모 시나리오와 심사위원 질문을 API로 검증하는 통합 테스트"""
import base64
import os
import tempfile
from pathlib import Path

os.environ["RROUTE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "public" / "samples"
GOOD_TEXT = "사이즈가 작아요. 한 번도 신지 않았고 포장 그대로입니다."


def img(name):
    return "data:image/jpeg;base64," + base64.b64encode((SAMPLES / name).read_bytes()).decode()


def analyze(cl, photo=None, **ret):
    rid = cl.post("/api/returns", json=ret).json()["return_id"]
    return rid, cl.post(f"/api/returns/{rid}/analyze", json={"image_base64": img(photo) if photo else None}).json()


def test_demo_flow():
    with TestClient(app) as cl:
        assert cl.get("/api/health").json()["ok"]
        rid, a = analyze(cl, "new.jpg")                                   # 1-4 접수 + AI 분석
        assert a["grade"] == "A" and a["verdict"].startswith("다음 구매자")
        d = cl.post(f"/api/returns/{rid}/decide").json()
        assert d["path"] == "direct", d
        m = cl.post("/api/match/run?explain=true").json()                 # 5-6 MCF 매칭
        assert m["status"] == "OPTIMAL" and m["saving"] > 0 and m["total_cost"] <= m["greedy_cost"]
        assert any(x["return_id"] == rid for x in m["matches"])
        i = cl.post("/api/inspections", json={"return_id": rid}).json()   # 7-8 검수 + QR
        v = cl.get(f"/api/verify/{i['qr_token']}").json()
        assert v["valid"] and [e["type"] for e in v["events"]][:2] == ["REQUESTED", "AI_GRADED"]
        bad = i["qr_token"][:-2] + ("AA" if not i["qr_token"].endswith("AA") else "BB")
        assert cl.get(f"/api/verify/{bad}").status_code == 400            # 위조 QR 거부
        assert cl.post(f"/api/returns/{rid}/deliver").json()["ok"]        # 9 재판매 완료
        assert cl.get("/api/kpi").json()["live"]["n"] == 1                # 10 KPI


def test_photo_changes_result():
    """심사위원 질문: 사진을 바꾸면 결과가 바뀌나요?"""
    with TestClient(app) as cl:
        _, new = analyze(cl, "new.jpg", reason_text=GOOD_TEXT)
        _, dark = analyze(cl, "dark_blurry.jpg", reason_text=GOOD_TEXT)
        _, none = analyze(cl, None, reason_text=GOOD_TEXT)
        photo = lambda a: next(c for c in a["contributions"] if c["key"] == "photo")["delta_pp"]
        assert new["resale_prob"] - dark["resale_prob"] > 0.1           # 10%p 이상 차이
        assert photo(new) > 0 > photo(dark)
        assert new["grade"] == "A" and dark["grade"] == "B"
        assert none["photo"] is None and "사진이 없어" in next(c for c in none["contributions"] if c["key"] == "photo")["note"]


def test_contributions_add_up():
    """심사위원 질문: 왜 이 값인가요? 기준값 + 기여도 합 = 최종값"""
    with TestClient(app) as cl:
        for photo in ["new.jpg", "dark_blurry.jpg", None]:
            _, a = analyze(cl, photo)
            total = a["baseline"] * 100 + sum(c["delta_pp"] for c in a["contributions"])
            assert abs(total - a["resale_prob"] * 100) < 0.3
        probs = {analyze(cl, p)[1]["resale_prob"] for p in ["new.jpg", "dark_blurry.jpg", None]}
        assert len(probs) == 3                                           # 95% 천장 같은 고정값 없음


def test_mismatch_blocks_direct():
    with TestClient(app) as cl:
        rid, a = analyze(cl, "new.jpg", reason_code="size", reason_text="사이즈가 작고 앞코에 얼룩이 있어요")
        assert a["mismatch"] == ["얼룩"] and a["grade"] != "A" and "허브에서 확인" in a["verdict"]
        d = cl.post(f"/api/returns/{rid}/decide").json()
        assert d["path"] != "direct" and "direct" in d["blocked"]


def test_damaged_sample_is_c():
    with TestClient(app) as cl:
        rid, a = analyze(cl, "stained.jpg", reason_code="damaged", reason_text="앞코에 얼룩이 생겼어요")
        assert a["grade"] == "C"
        assert next(c for c in a["contributions"] if c["key"] == "photo")["delta_pp"] <= 1.0   # 선명한 파손 사진이 점수를 올리지 않음
        assert cl.post(f"/api/returns/{rid}/decide").json()["path"] not in ("direct", "hub_storage")


def test_restricted_never_direct():
    with TestClient(app) as cl:
        rid, _ = analyze(cl, "new.jpg", sku="SKU-SERUM")
        assert cl.post(f"/api/returns/{rid}/decide").json()["path"] not in ("direct", "hub_storage")


def test_counterexample_nearest_first_is_worse():
    """심사위원 질문: 가장 가까운 주문으로 보내면 되지 않나요?"""
    with TestClient(app) as cl:
        cx = cl.get("/api/scenario/counterexample").json()
        g, o = cx["nearest_first"], cx["min_cost_flow"]
        assert g["total_cost"] - o["total_cost"] > 15000 and o["km"] < g["km"] / 10
        assert any(l["kind"] == "seller_return" for l in g["legs"]) and all(l["kind"] == "reallocate" for l in o["legs"])
        assert {p["order_id"] for p in g["pairs"] if p["return_id"] == "RT-CX-A"} == {"OD-CX-P"}   # 가까운 순: A가 P를 가져감
        assert {p["order_id"] for p in o["pairs"] if p["return_id"] == "RT-CX-A"} == {"OD-CX-Q"}   # 최적: A는 Q로


def test_model_info():
    with TestClient(app) as cl:
        m = cl.get("/api/model").json()
        assert m["metrics"]["n_train"] == 4800 and len(m["limitations"]) == 3


def test_simulate_endpoint():
    with TestClient(app) as cl:
        s = cl.post("/api/simulate", json={"days": 10, "orders_per_day": 2000}).json()
        assert s["kpi"]["반품 1건 물류비(원)"]["rroute"] < s["kpi"]["반품 1건 물류비(원)"]["baseline"]
