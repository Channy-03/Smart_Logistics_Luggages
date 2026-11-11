"""비용 파라미터 (시뮬레이션 r_route_sim.py와 동일한 가정값)."""
LEG_FIXED = 2500          # 집하/배송 1회 (원)
LINEHAUL_PER_KM = 30      # 간선 km당 (원/건)
INSP_SELLER, INSP_HUB = 2000, 1000
RESTOCK, HUB_HANDLING, HUB_STORAGE_PER_DAY = 500, 500, 200
CO2_LEG, CO2_PER_KM = 0.18, 0.0012  # kgCO2
CARBON_PRICE = 15         # 원/kgCO2 (배출권 가격 수준 가정)
DEP_PER_DAY = {"fashion": .004, "electronics": .003, "living": .001, "beauty": .002, "food": .010}
RECOVERY = {"direct": .95, "hub_storage": .95, "seller_return": .95, "refurbish": .55, "donation": .0, "disposal": .0}
DIRECT_THRESHOLD = .75
MATCH_RADIUS_KM = 25


def ship(km: float, legs: int = 1) -> float:
    return legs * LEG_FIXED + LINEHAUL_PER_KM * km


def co2(km: float, legs: int = 1) -> float:
    return legs * CO2_LEG + CO2_PER_KM * km
