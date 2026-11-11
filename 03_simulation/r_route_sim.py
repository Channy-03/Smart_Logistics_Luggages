"""
R_ROUTE 창원시 반품 시뮬레이션 (기존 반품 방식 vs R_ROUTE)

모든 수치는 공개 통계/문헌 수준의 '가정값'이며 실제 기업 데이터가 아니다.
가정값은 PARAMS 한 곳에 모여 있고, 민감도 분석으로 결론의 견고성을 확인한다.

실행:  python r_route_sim.py            -> 기본 시나리오 + 민감도 분석 결과(csv) 출력
구조:
  1) generate_world()   : 창원시 고객·거점·SKU·판매자 창고 생성
  2) generate_orders()  : 30일간 주문 생성 (SKU 인기도 = Zipf)
  3) generate_returns() : 반품 15%, 직송가능(AI 판정 통과) 20%
  4) run_baseline()     : 모든 반품 -> 판매자 창고 복귀
  5) run_rroute()       : 직송가능 반품 -> 거점 -> 동일 SKU 신규주문에 재할당 (시간 배치별 최소비용 배정)
  6) kpis()             : 8개 KPI 산출
"""
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

PARAMS = dict(
    seed=42,
    days=30,
    orders_per_day=2000,        # 창원시 내 1개 플랫폼(또는 3PL) 고객사 묶음의 일 주문량 (가정)
    n_sku=2000,
    zipf_s=1.1,                 # SKU 인기도 쏠림
    return_rate=0.15,
    direct_ratio=0.20,          # 반품 중 AI 판정으로 '직송 가능' 판정 비율
    n_hubs=10,
    hold_hours=72,              # 거점 보관 한도
    national_mult=50,           # 전국 수요 = 창원 수요 x 50 (인구비 약 2%)
    # 비용 (원)
    leg_fixed=2500,             # 집하 또는 배송 1회(라스트마일) 고정비
    linehaul_per_km=30,         # 간선 km당 비용(건당)
    insp_seller=2000, insp_hub=1000,
    restock=500, hub_handling=500, hub_storage_per_day=200,
    # 탄소
    co2_leg=0.18,               # kgCO2 / 라스트마일 1회
    co2_per_km=0.0012,          # kgCO2 / 건-km (간선)
    # 회수
    pickup_success=0.85,        # 방문 회수 1차 성공률
    dropoff_share=0.60,         # R_ROUTE 직송가능 고객 중 거점 직접 반납 선택 비율
    detour=1.3,                 # 직선거리 -> 도로거리 보정
)

# 창원시 5개 구 중심(km 평면 좌표, 대략) 과 인구 가중치
DISTRICTS = {
    "의창구": ((8, 14), 0.22), "성산구": ((12, 10), 0.24), "마산합포구": ((0, 4), 0.17),
    "마산회원구": ((2, 9), 0.18), "진해구": ((20, 2), 0.19),
}
# 판매자 창고 권역: (창원 기준 도로거리 km, 비중)
SELLER_REGIONS = {"수도권": (300, 0.60), "대구": (110, 0.15), "부산·김해": (45, 0.15), "창원": (12, 0.10)}
CATEGORIES = {  # 이름: (비중, 평균가격, 일 가치하락률, 위생제한)
    "패션": (0.35, 45000, 0.004, False), "전자": (0.15, 120000, 0.003, False),
    "생활": (0.25, 25000, 0.001, False), "뷰티": (0.15, 30000, 0.002, True),
    "식품": (0.10, 20000, 0.010, True),
}


def generate_world(P, rng):
    names = list(DISTRICTS)
    w = np.array([DISTRICTS[n][1] for n in names])
    # 고객 후보 위치 풀
    n = 20000
    d = rng.choice(len(names), n, p=w / w.sum())
    centers = np.array([DISTRICTS[names[i]][0] for i in d], float)
    cust = centers + rng.normal(0, 2.0, (n, 2))
    # 거점 10개: 고객 분포에 대한 k-means (p-median 근사)
    hubs = cust[rng.choice(n, P["n_hubs"], replace=False)].copy()
    for _ in range(30):
        lab = np.argmin(((cust[:, None] - hubs[None]) ** 2).sum(-1), 1)
        for k in range(P["n_hubs"]):
            if (lab == k).any():
                hubs[k] = cust[lab == k].mean(0)
    # SKU
    cats = list(CATEGORIES)
    cw = np.array([CATEGORIES[c][0] for c in cats])
    sku_cat = rng.choice(len(cats), P["n_sku"], p=cw)
    sku_price = np.array([rng.lognormal(np.log(CATEGORIES[cats[c]][1]), 0.5) for c in sku_cat])
    regs = list(SELLER_REGIONS)
    rw = np.array([SELLER_REGIONS[r][1] for r in regs])
    sku_seller_km = np.array([SELLER_REGIONS[regs[i]][0] for i in rng.choice(len(regs), P["n_sku"], p=rw)], float)
    pop = 1 / np.arange(1, P["n_sku"] + 1) ** P["zipf_s"]
    pop /= pop.sum()
    return dict(cust=cust, hubs=hubs, cats=cats, sku_cat=sku_cat, sku_price=sku_price,
                sku_seller_km=sku_seller_km, pop=pop)


def generate_orders(P, W, rng):
    n = P["days"] * P["orders_per_day"]
    t = np.sort(rng.uniform(0, P["days"] * 24, n))  # 시간(h)
    sku = rng.choice(P["n_sku"], n, p=W["pop"])
    loc = W["cust"][rng.integers(0, len(W["cust"]), n)]
    return pd.DataFrame(dict(t=t, sku=sku, x=loc[:, 0], y=loc[:, 1]))


def generate_returns(P, W, orders, rng):
    is_ret = rng.random(len(orders)) < P["return_rate"]
    R = orders[is_ret].copy().reset_index(drop=True)
    R["t_req"] = R.t + 24 + rng.lognormal(np.log(72), 0.5, len(R))  # 수령 후 평균 약 3일 뒤 반품 신청
    cat = W["sku_cat"][R.sku]
    hyg = np.array([CATEGORIES[W["cats"][c]][3] for c in cat])
    # 위생 품목 제외 후 전체 비율이 direct_ratio가 되도록 보정
    p_ok = min(1.0, P["direct_ratio"] / max(1e-9, (~hyg).mean()))
    R["eligible"] = (~hyg) & (rng.random(len(R)) < p_ok)
    R["price"] = W["sku_price"][R.sku]
    R["dep"] = [CATEGORIES[W["cats"][c]][2] for c in cat]
    R["seller_km"] = W["sku_seller_km"][R.sku]
    xy = R[["x", "y"]].to_numpy()
    hd = np.sqrt(((xy[:, None] - W["hubs"][None]) ** 2).sum(-1)) * P["detour"]
    R["hub"] = hd.argmin(1)
    R["hub_km"] = hd.min(1)
    # 판매자까지 운송일수
    R["transit_d"] = np.select([R.seller_km <= 50, R.seller_km <= 150], [1, 1.5], 2)
    # 전국 기준 동일 SKU 다음 주문까지 대기(일): 지수분포
    lam_nat = W["pop"][R.sku] * P["orders_per_day"] * P["national_mult"]
    R["wait_nat_d"] = rng.exponential(1 / lam_nat)
    R["pick_ok"] = rng.random(len(R)) < P["pickup_success"]
    R["dropoff"] = rng.random(len(R)) < P["dropoff_share"]
    return R


def run_baseline(P, R):
    out = pd.DataFrame(index=R.index)
    km = R.seller_km
    out["km"] = km                                         # 반품 1건 이동거리
    out["ship"] = (P["leg_fixed"] + P["linehaul_per_km"] * km).astype(float)
    out["handling"] = float(P["insp_seller"] + P["restock"])
    out["co2"] = P["co2_leg"] + P["co2_per_km"] * km
    out["refund_d"] = 1 + R.transit_d + 2 + 1             # 회수1 + 운송 + 검수대기2 + 환불처리1
    out["resale_d"] = 1 + R.transit_d + 2 + 1 + R.wait_nat_d
    out["limbo_d"] = 1 + R.transit_d + 2 + 1               # 판매 불가 상태 체류일
    out["collect_ok"] = R.pick_ok.astype(bool)
    out["path"] = "판매자 복귀"
    # 직송 매칭 시 신규 재고가 대신 나갔어야 할 배송(비교 공정성): baseline에서는 신규 주문이 판매자 창고에서 출고
    return out


def run_rroute(P, R, orders, W):
    out = run_baseline(P, R).copy()
    E = R[R.eligible].copy()
    E["avail"] = E.t_req + 24                               # 거점 도착·검수 완료
    E["expire"] = E.avail + P["hold_hours"]
    hubs = W["hubs"]
    matched = {}                                            # return idx -> (order idx, match time, km to buyer)
    pool_by_sku = {}
    ev = E.sort_values("avail")
    ev_i = 0
    O = orders.reset_index(drop=True)
    O["hour"] = O.t.astype(int)
    used_orders = set()
    ev_list = list(zip(ev.index, ev.avail, ev.expire, ev.sku, ev.hub))
    for h, grp in O.groupby("hour"):
        while ev_i < len(ev_list) and ev_list[ev_i][1] <= h:
            ridx, a, e, s, hb = ev_list[ev_i]
            pool_by_sku.setdefault(s, []).append((ridx, e, hb))
            ev_i += 1
        for s, g in grp.groupby("sku"):
            pool = [p for p in pool_by_sku.get(s, []) if p[1] > h]
            pool_by_sku[s] = pool
            if not pool:
                continue
            oxy = g[["x", "y"]].to_numpy()
            hxy = hubs[[p[2] for p in pool]]
            C = np.sqrt(((hxy[:, None] - oxy[None]) ** 2).sum(-1)) * P["detour"]
            ri, oi = linear_sum_assignment(C)               # 헝가리안(배치 내 최소비용 배정)
            taken = set()
            for a_, b_ in zip(ri, oi):
                ridx = pool[a_][0]
                matched[ridx] = (g.index[b_], h, C[a_, b_])
                taken.add(a_)
            pool_by_sku[s] = [p for k, p in enumerate(pool) if k not in taken]
    for ridx, r in E.iterrows():
        drop = r.dropoff
        first = 0 if drop else P["leg_fixed"]               # 거점 반납이면 집하비 없음
        c_ok = True if drop else r.pick_ok
        to_hub_km = r.hub_km
        if ridx in matched:
            _, mt, km_b = matched[ridx]
            # 반품: 고객->거점->다음 구매자 / 기존: 고객->판매자 + 판매자->다음 구매자(신규재고)
            km = to_hub_km + km_b
            ship = first + P["leg_fixed"] + P["linehaul_per_km"] * km
            # 기존 방식이었다면 그 구매자에게 판매자 창고에서 나갔을 배송을 절감분으로 차감
            ship -= P["leg_fixed"] + P["linehaul_per_km"] * r.seller_km
            km -= r.seller_km
            stay = (mt - r.avail) / 24
            out.loc[ridx, ["km", "ship"]] = [km, ship]
            out.loc[ridx, "handling"] = P["insp_hub"] + P["hub_handling"] + P["hub_storage_per_day"] * stay
            out.loc[ridx, "co2"] = (0 if drop else P["co2_leg"]) + P["co2_leg"] + P["co2_per_km"] * (to_hub_km + km_b) \
                - (P["co2_leg"] + P["co2_per_km"] * r.seller_km)
            out.loc[ridx, "resale_d"] = (mt - r.t_req) / 24 + 1
            out.loc[ridx, "limbo_d"] = (mt - r.t_req) / 24
            out.loc[ridx, "path"] = "다음 구매자 직송"
        else:
            km = to_hub_km + r.seller_km
            out.loc[ridx, "km"] = km
            out.loc[ridx, "ship"] = first + P["leg_fixed"] + P["linehaul_per_km"] * km
            out.loc[ridx, "handling"] = P["insp_hub"] + P["hub_handling"] + P["hub_storage_per_day"] * P["hold_hours"] / 24 + P["restock"]
            out.loc[ridx, "co2"] = (0 if drop else P["co2_leg"]) + P["co2_leg"] + P["co2_per_km"] * km
            hold_d = P["hold_hours"] / 24
            out.loc[ridx, "resale_d"] = 1 + hold_d + r.transit_d + 1 + r.wait_nat_d
            out.loc[ridx, "limbo_d"] = 1 + hold_d + r.transit_d + 1
            out.loc[ridx, "path"] = "거점 보관 후 판매자 복귀"
        out.loc[ridx, "refund_d"] = 2.0                     # 거점 검수 완료 = 반환 간주 -> 즉시 환불
        out.loc[ridx, "collect_ok"] = c_ok
    return out


def kpis(R, B, X, P):
    def k(D, name):
        val = (R.price * R.dep * D.limbo_d)
        return {
            "시나리오": name,
            "반품 1건 평균 이동거리(km)": D.km.mean(),
            "반품 1건 배송비(원)": D.ship.mean(),
            "반품 1건 물류비(원)": (D.ship + D.handling).mean(),
            "반품 1건 가치하락(원)": val.mean(),
            "평균 환불 소요(일)": D.refund_d.mean(),
            "직송가능 반품 재판매 소요(일)": D.resale_d[R.eligible].mean(),
            "반품 1건 CO2(kg)": D.co2.mean(),
            "회수 1차 성공률(%)": 100 * D.collect_ok.mean(),
            "반품재고 회전율(회/월)": 30 / D.limbo_d.mean(),
            "직송 매칭률(%, 직송가능 대비)": 100 * (D.path[R.eligible] == "다음 구매자 직송").mean(),
        }
    return pd.DataFrame([k(B, "기존 방식"), k(X, "R_ROUTE")]).set_index("시나리오").T


def simulate(**over):
    P = {**PARAMS, **over}
    rng = np.random.default_rng(P["seed"])
    W = generate_world(P, rng)
    O = generate_orders(P, W, rng)
    R = generate_returns(P, W, O, rng)
    B = run_baseline(P, R)
    X = run_rroute(P, R, O, W)
    return P, W, O, R, B, X


if __name__ == "__main__":
    P, W, O, R, B, X = simulate()
    K = kpis(R, B, X, P)
    K["개선율(%)"] = (K["R_ROUTE"] - K["기존 방식"]) / K["기존 방식"] * 100
    pd.set_option("display.width", 200)
    print(f"주문 {len(O):,}건 / 반품 {len(R):,}건 / 직송가능 {int(R.eligible.sum()):,}건")
    print(X.path.value_counts())
    print(K.round(2))
    K.round(3).to_csv("kpi_base.csv", encoding="utf-8-sig")
    # 민감도 분석
    rows = []
    for hold in [24, 48, 72, 120]:
        for opd in [1000, 2000, 4000]:
            P2, W2, O2, R2, B2, X2 = simulate(hold_hours=hold, orders_per_day=opd)
            K2 = kpis(R2, B2, X2, P2)
            rows.append(dict(hold_hours=hold, orders_per_day=opd,
                             match_pct=K2.loc["직송 매칭률(%, 직송가능 대비)", "R_ROUTE"],
                             km_cut_pct=100 * (1 - K2.loc["반품 1건 평균 이동거리(km)", "R_ROUTE"] / K2.loc["반품 1건 평균 이동거리(km)", "기존 방식"]),
                             cost_cut_pct=100 * (1 - K2.loc["반품 1건 물류비(원)", "R_ROUTE"] / K2.loc["반품 1건 물류비(원)", "기존 방식"]),
                             resale_d_R=K2.loc["직송가능 반품 재판매 소요(일)", "R_ROUTE"],
                             resale_d_B=K2.loc["직송가능 반품 재판매 소요(일)", "기존 방식"]))
    S = pd.DataFrame(rows)
    print(S.round(2))
    S.round(3).to_csv("sensitivity.csv", index=False, encoding="utf-8-sig")
    rows = []
    for dr in [0.1, 0.2, 0.3, 0.4]:
        P3, W3, O3, R3, B3, X3 = simulate(direct_ratio=dr)
        K3 = kpis(R3, B3, X3, P3)
        rows.append(dict(direct_ratio=dr,
                         km_cut_pct=100 * (1 - K3.loc["반품 1건 평균 이동거리(km)", "R_ROUTE"] / K3.loc["반품 1건 평균 이동거리(km)", "기존 방식"]),
                         cost_cut_pct=100 * (1 - K3.loc["반품 1건 물류비(원)", "R_ROUTE"] / K3.loc["반품 1건 물류비(원)", "기존 방식"]),
                         co2_cut_pct=100 * (1 - K3.loc["반품 1건 CO2(kg)", "R_ROUTE"] / K3.loc["반품 1건 CO2(kg)", "기존 방식"])))
    D = pd.DataFrame(rows)
    print(D.round(2))
    D.round(3).to_csv("sensitivity_direct_ratio.csv", index=False, encoding="utf-8-sig")
