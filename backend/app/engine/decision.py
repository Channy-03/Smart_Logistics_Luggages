"""Decision Engine: 6개 처리 경로의 기대 순가치 V_k 를 계산하고 최댓값 경로를 고른다.

V_k = p * R_k * price - (1-p) * F_k - T_k - I_k - price * dep * t_k - λ * E_k   (+ 회피된 신규출고 비용)
"""
import math

from . import costs as C

PATHS = ["direct", "hub_storage", "seller_return", "refurbish", "donation", "disposal"]
LABELS = {"direct": "Direct Reallocation", "hub_storage": "Hub Storage", "seller_return": "Seller Return",
          "refurbish": "Refurbish", "donation": "Donation", "disposal": "Disposal"}
FAIL_COST = {"direct": 15000, "hub_storage": 8000, "seller_return": 0, "refurbish": 0, "donation": 0, "disposal": 0}


def decide(p, price, category, restricted, seller_km, km_customer_hub, nearest_order_km, open_orders_same_sku, hold_hours=72,
           mismatch=False):
    dep = C.DEP_PER_DAY.get(category, .002)
    out = {}

    def v(path, km, legs, insp, days, extra_credit=0.0):
        T = C.ship(km, legs)
        E = C.co2(km, legs)
        return (p * C.RECOVERY[path] * price - (1 - p) * FAIL_COST[path] - T - insp
                - price * dep * days - C.CARBON_PRICE * E + extra_credit)

    # 기준: 판매자 복귀
    out["seller_return"] = v("seller_return", seller_km, 1, C.INSP_SELLER + C.RESTOCK, 5.6)
    can_local = (not restricted) and p >= C.DIRECT_THRESHOLD
    if can_local and nearest_order_km is not None and not mismatch:  # 사유·상세 사유 불일치면 직송 금지
        # 신규 재고 출고(판매자->구매자)를 대체하므로 그 비용을 크레딧으로 더한다
        credit = C.ship(seller_km) + C.CARBON_PRICE * C.co2(seller_km)
        out["direct"] = v("direct", km_customer_hub + nearest_order_km, 2, C.INSP_HUB + C.HUB_HANDLING, 1.5, credit)
    else:
        out["direct"] = None
    if can_local:
        # 보관 한도 내 동일 SKU 주문 도착 확률 q (포아송 근사; 일 수요율 = 열린 주문 수 기반)
        rate_per_day = max(.05, open_orders_same_sku * .5)
        q = 1 - math.exp(-rate_per_day * hold_hours / 24)
        credit = C.ship(seller_km)
        matched = v("hub_storage", km_customer_hub + 6, 2, C.INSP_HUB + C.HUB_HANDLING + C.HUB_STORAGE_PER_DAY * 1.5, 2.5, credit)
        fallback = out["seller_return"] - C.ship(km_customer_hub) - C.HUB_HANDLING - C.HUB_STORAGE_PER_DAY * hold_hours / 24
        out["hub_storage"] = q * matched + (1 - q) * fallback
    else:
        out["hub_storage"] = None
    out["refurbish"] = v("refurbish", seller_km, 1, 3000, 10)
    out["donation"] = v("donation", 10, 1, 0, 3) + .10 * price * (1 - p * .5)  # 기부금 세제 효과 가정
    out["disposal"] = v("disposal", 5, 1, 1500, 1)

    valid = {k: round(x) for k, x in out.items() if x is not None}
    best = max(valid, key=valid.get)
    reason = {
        "direct": f"재판매 가능성 {p:.0%}, 반경 내 같은 상품 주문 {nearest_order_km:.1f}km" if nearest_order_km is not None else "",
        "hub_storage": "반품 사유와 상세 사유가 맞지 않아 허브에서 실물을 확인한 뒤 판매" if mismatch
        else "가능성은 충분하나 지금 근처에 같은 상품 주문이 없어 허브에서 대기",
        "seller_return": "재판매 가능성이 직송 기준(75%)보다 낮거나 위생 품목이라 판매자가 직접 검수",
        "refurbish": "상태 저하, 리퍼 후 재판매가 유리",
        "donation": "재판매 가치보다 기부 효과가 큼",
        "disposal": "회수 가치 없음",
    }[best]
    return {"path": best, "label": LABELS[best], "expected_values": valid,
            "blocked": [k for k, x in out.items() if x is None], "reason": reason}
