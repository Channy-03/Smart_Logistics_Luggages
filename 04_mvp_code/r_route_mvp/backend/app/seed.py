"""창원시 데모 월드 시드: 허브 10곳, 상품, 열린 주문, 데모 반품 케이스.
허브 좌표는 행정동 중심 부근의 가상 위치이며 실제 제휴처가 아니다."""
import math
import random
from datetime import datetime, timedelta, timezone

from .db import conn, init_db, now

HUBS = [
    ("H01", "감계 허브", "locker", 35.3285, 128.6470),
    ("H02", "팔용 허브", "sub_terminal", 35.2465, 128.6295),
    ("H03", "용지 허브", "convenience_store", 35.2360, 128.6680),
    ("H04", "상남 허브", "convenience_store", 35.2212, 128.6808),
    ("H05", "가음정 허브", "convenience_store", 35.2161, 128.7004),
    ("H06", "양덕 허브", "convenience_store", 35.2242, 128.5826),
    ("H07", "내서 허브", "locker", 35.2540, 128.5150),
    ("H08", "오동 허브", "convenience_store", 35.2003, 128.5713),
    ("H09", "월영 허브", "locker", 35.1823, 128.5590),
    ("H10", "진해 석동 허브", "sub_terminal", 35.1500, 128.6870),
]

SELLERS = {"수도권": 300, "대구": 110, "부산·김해": 45, "창원": 12}

# (sku, name, category, price, seller_region, restricted)
PRODUCTS = [
    ("SKU-AF270", "나이키 에어포스 1 '07 270mm", "fashion", 129000, "수도권", 0),
    ("SKU-AF265", "나이키 에어포스 1 '07 265mm", "fashion", 129000, "수도권", 0),
    ("SKU-HD-M", "베이직 후드티 M", "fashion", 39000, "수도권", 0),
    ("SKU-HD-L", "베이직 후드티 L", "fashion", 39000, "수도권", 0),
    ("SKU-DN-30", "와이드 데님 30", "fashion", 59000, "대구", 0),
    ("SKU-BUDS", "무선 이어버드 화이트", "electronics", 89000, "수도권", 0),
    ("SKU-KB01", "기계식 키보드 87키", "electronics", 119000, "수도권", 0),
    ("SKU-AIR", "에어프라이어 5L", "living", 79000, "부산·김해", 0),
    ("SKU-TUM", "스테인리스 텀블러 500ml", "living", 25000, "창원", 0),
    ("SKU-LMP", "LED 무드등", "living", 32000, "대구", 0),
    ("SKU-SERUM", "비타민 세럼 30ml", "beauty", 28000, "수도권", 1),
    ("SKU-SNACK", "견과류 선물세트", "food", 35000, "부산·김해", 1),
]

NAMES = ["김*진", "이*현", "박*수", "최*영", "정*호", "강*민", "조*아", "윤*서", "장*우", "임*희",
         "한*결", "오*빈", "서*연", "신*훈", "권*지", "황*율"]


def haversine_km(a_lat, a_lng, b_lat, b_lng):
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def road_km(a_lat, a_lng, b_lat, b_lng, detour=1.3):
    """MVP는 직선거리 x 우회계수. 운영은 OSRM 도로거리 행렬로 교체."""
    return haversine_km(a_lat, a_lng, b_lat, b_lng) * detour


def nearest_hub(c, lat, lng):
    hubs = [dict(r) for r in c.execute("SELECT * FROM hubs").fetchall()]
    return min(hubs, key=lambda h: haversine_km(lat, lng, h["lat"], h["lng"]))


def _jitter(rng, lat, lng, km=1.6):
    return lat + rng.gauss(0, km / 111), lng + rng.gauss(0, km / 91)


def seed(reset: bool = True, n_orders: int = 36, rng_seed: int = 7):
    init_db(reset=reset)
    rng = random.Random(rng_seed)
    t0 = datetime.now(timezone.utc)
    with conn() as c:
        c.executemany("INSERT INTO hubs VALUES (?,?,?,?,?,40)", HUBS)
        for sku, name, cat, price, region, restricted in PRODUCTS:
            c.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)",
                      (sku, name, cat, price, f"seller-{region}", region, SELLERS[region], restricted))
        weights = [10, 6, 6, 5, 4, 5, 3, 3, 4, 3, 3, 2]
        skus = [p[0] for p in PRODUCTS]
        for i in range(n_orders):
            hub = rng.choice(HUBS)
            lat, lng = _jitter(rng, hub[3], hub[4])
            sku = rng.choices(skus, weights)[0]
            c.execute("INSERT INTO orders (order_id, sku, buyer_name, lat, lng, created_at, accepts_inspected_return)"
                      " VALUES (?,?,?,?,?,?,?)",
                      (f"OD-{2611000 + i}", sku, rng.choice(NAMES), lat, lng,
                       (t0 - timedelta(minutes=rng.randint(1, 240))).isoformat(timespec="seconds"),
                       1 if rng.random() < 0.8 else 0))
        # 데모 핵심: 상남동 인근, 에어포스 270을 기다리는 주문 3건 (거리 다름)
        for oid, name, (lat, lng) in [("OD-2611901", "이*현", (35.2236, 128.6890)),
                                       ("OD-2611902", "박*수", (35.2420, 128.6320)),
                                       ("OD-2611903", "정*호", (35.1980, 128.5760))]:
            c.execute("INSERT INTO orders (order_id, sku, buyer_name, lat, lng, created_at, accepts_inspected_return)"
                      " VALUES (?,?,?,?,?,?,1)", (oid, "SKU-AF270", name, lat, lng, now()))
        # 배경 반품 풀(ATP에 이미 편입된 반품) - 매칭 엔진이 함께 푼다
        bg = [("RT-BG-01", "SKU-HD-M", "H06"), ("RT-BG-02", "SKU-BUDS", "H03"), ("RT-BG-03", "SKU-AF265", "H08"),
              ("RT-BG-04", "SKU-AIR", "H05"), ("RT-BG-05", "SKU-HD-L", "H02"), ("RT-BG-06", "SKU-TUM", "H09")]
        for rid, sku, hid in bg:
            h = next(x for x in HUBS if x[0] == hid)
            lat, lng = _jitter(rng, h[3], h[4], 0.8)
            c.execute("INSERT INTO returns (return_id, order_ref, sku, customer_name, lat, lng, reason_code, reason_text,"
                      " days_since_purchase, created_at, status, nearest_hub) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (rid, "OD-PAST", sku, rng.choice(NAMES), lat, lng, "size", "사이즈 교환", 3, now(), "atp", hid))
            c.execute("INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (rid, 0.86, "A", "다음 구매자에게 바로 보낼 수 있어요", 0.47, "[]", "[]", None, "seed", now()))
            c.execute("INSERT INTO atp_inventory VALUES (?,?,?,?,?,?,?)",
                      (rid, sku, hid, 0.86, now(), (t0 + timedelta(hours=72)).isoformat(timespec="seconds"), "at_hub"))


if __name__ == "__main__":
    seed()
    print("seeded")
