"""Min Cost Flow Optimizer (Google OR-Tools SimpleMinCostFlow)

네트워크
  공급: 반품 노드 r_i (+1), 신규재고 노드 NEW (+|O|)
  수요: 주문 노드 o_j (-1), 판매자 복귀 노드 SELLER (-|R|)
  간선
    r_i -> o_j   : 허브->구매자 배송 + 허브 처리비      (같은 SKU, 구매자 동의, 반경 내)
    r_i -> SELLER: 판매자 복귀 운송 + 정밀 검수 + 재입고
    NEW -> o_j   : 판매자 창고 -> 구매자 신규 출고
    NEW -> SELLER: 0 (쓰이지 않은 신규 재고)
목적: 총 실제 비용 최소화. 매칭이 없어도 해(전량 판매자 복귀 + 전량 신규 출고)가 항상 존재한다.
"""
from __future__ import annotations

from ortools.graph.python import min_cost_flow

from . import costs as C
from ..seed import road_km


def solve(returns: list[dict], orders: list[dict], hubs: dict, products: dict, explain: bool = False):
    R, O = len(returns), len(orders)
    NEW, SELLER = R + O, R + O + 1
    smcf = min_cost_flow.SimpleMinCostFlow()
    arcs = []

    def add(u, v, cap, cost, kind, meta):
        a = smcf.add_arc_with_capacity_and_unit_cost(u, v, cap, int(round(cost)))
        arcs.append(dict(arc=a, u=u, v=v, cost=int(round(cost)), kind=kind, **meta))

    for i, r in enumerate(returns):
        h = hubs[r["hub_id"]]
        p = products[r["sku"]]
        add(i, SELLER, 1, C.ship(p["seller_km"]) + C.INSP_SELLER + C.RESTOCK, "return_to_seller", {"return_id": r["return_id"]})
        for j, o in enumerate(orders):
            if o["sku"] != r["sku"] or not o["accepts_inspected_return"]:
                continue
            km = road_km(h["lat"], h["lng"], o["lat"], o["lng"])
            if km > C.MATCH_RADIUS_KM:
                continue
            add(i, R + j, 1, C.ship(km) + C.HUB_HANDLING, "reallocate",
                {"return_id": r["return_id"], "order_id": o["order_id"], "km": round(km, 2), "hub_id": r["hub_id"]})
    for j, o in enumerate(orders):
        add(NEW, R + j, 1, C.ship(products[o["sku"]]["seller_km"]), "new_stock", {"order_id": o["order_id"]})
    add(NEW, SELLER, O, 0, "unused_new", {})
    for i in range(R):
        smcf.set_node_supply(i, 1)
    for j in range(O):
        smcf.set_node_supply(R + j, -1)
    smcf.set_node_supply(NEW, O)
    smcf.set_node_supply(SELLER, -R)

    status = smcf.solve()
    if status != smcf.OPTIMAL:
        raise RuntimeError(f"min cost flow status {status}")
    baseline = sum(a["cost"] for a in arcs if a["kind"] in ("return_to_seller", "new_stock"))
    matches = []
    for a in arcs:
        a["flow"] = smcf.flow(a["arc"])
        if a["kind"] == "reallocate" and a["flow"] > 0:
            r = next(x for x in returns if x["return_id"] == a["return_id"])
            o = next(x for x in orders if x["order_id"] == a["order_id"])
            p = products[r["sku"]]
            saved_cost = (C.ship(p["seller_km"]) + C.INSP_SELLER + C.RESTOCK + C.ship(p["seller_km"])) - a["cost"]
            saved_km = 2 * p["seller_km"] - a["km"]
            matches.append(dict(return_id=r["return_id"], order_id=o["order_id"], hub_id=a["hub_id"], km_hub_buyer=a["km"],
                                cost_saved=int(saved_cost), km_saved=round(saved_km, 1),
                                co2_saved=round(C.co2(p["seller_km"]) * 2 - C.co2(a["km"]), 3)))
    g = greedy(returns, orders, hubs, products)
    result = dict(status="OPTIMAL", n_returns=R, n_orders=O, total_cost=smcf.optimal_cost(),
                  baseline_cost=baseline, saving=baseline - smcf.optimal_cost(), matches=matches,
                  greedy_cost=g["total_cost"], greedy_pairs=g["pairs"],
                  km_reallocated=round(sum(m["km_hub_buyer"] for m in matches), 2))
    if explain:
        names = {i: r["return_id"] for i, r in enumerate(returns)} | {R + j: o["order_id"] for j, o in enumerate(orders)} \
            | {NEW: "NEW_STOCK", SELLER: "SELLER_RETURN"}
        result["graph"] = {
            "nodes": [{"id": names[k], "type": "return" if k < R else ("order" if k < R + O else names[k].lower())}
                      for k in range(R + O + 2)],
            "arcs": [{"from": names[a["u"]], "to": names[a["v"]], "cost": a["cost"], "flow": a["flow"], "kind": a["kind"]}
                     for a in arcs if a["kind"] != "unused_new"],
        }
    return result


def greedy(returns: list[dict], orders: list[dict], hubs: dict, products: dict):
    """비교 기준: 반품이 들어온 순서대로 '가장 가까운 같은 상품 주문'을 하나씩 가져가는 방식."""
    taken, pairs, cost, km = set(), [], 0.0, 0.0
    for r in returns:
        h, p = hubs[r["hub_id"]], products[r["sku"]]
        cands = [(road_km(h["lat"], h["lng"], o["lat"], o["lng"]), o) for o in orders
                 if o["sku"] == r["sku"] and o["accepts_inspected_return"] and o["order_id"] not in taken]
        cands = [c for c in cands if c[0] <= C.MATCH_RADIUS_KM]
        if cands:
            d, o = min(cands, key=lambda c: c[0])
            taken.add(o["order_id"]); pairs.append({"return_id": r["return_id"], "order_id": o["order_id"], "km": round(d, 2)})
            cost += int(round(C.ship(d) + C.HUB_HANDLING)); km += d
        else:
            cost += int(round(C.ship(p["seller_km"]) + C.INSP_SELLER + C.RESTOCK))
    for o in orders:
        if o["order_id"] not in taken:
            cost += int(round(C.ship(products[o["sku"]]["seller_km"])))
    return {"total_cost": int(round(cost)), "km_reallocated": round(km, 2), "pairs": pairs}
