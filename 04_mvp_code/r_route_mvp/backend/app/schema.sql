-- R_ROUTE MVP schema (SQLite). 운영 환경은 PostgreSQL + PostGIS로 동일 구조 이전.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS hubs (
  hub_id        TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  hub_type      TEXT NOT NULL,              -- convenience_store | locker | sub_terminal
  lat           REAL NOT NULL,
  lng           REAL NOT NULL,
  capacity      INTEGER NOT NULL DEFAULT 40
);

CREATE TABLE IF NOT EXISTS products (
  sku           TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  category      TEXT NOT NULL,              -- fashion | electronics | living | beauty | food
  price         INTEGER NOT NULL,
  seller_id     TEXT NOT NULL,
  seller_region TEXT NOT NULL,              -- 수도권 | 대구 | 부산·김해 | 창원
  seller_km     REAL NOT NULL,              -- 창원 기준 도로거리
  restricted    INTEGER NOT NULL DEFAULT 0  -- 위생/규제 품목(직송 금지)
);

CREATE TABLE IF NOT EXISTS orders (
  order_id      TEXT PRIMARY KEY,
  sku           TEXT NOT NULL REFERENCES products(sku),
  buyer_name    TEXT NOT NULL,
  lat           REAL NOT NULL,
  lng           REAL NOT NULL,
  created_at    TEXT NOT NULL,
  accepts_inspected_return INTEGER NOT NULL DEFAULT 1,  -- '검수 완료 반품' 수령 동의
  status        TEXT NOT NULL DEFAULT 'open',            -- open | matched | fulfilled_new
  fulfilled_by  TEXT                                    -- return_id or 'seller'
);

CREATE TABLE IF NOT EXISTS returns (
  return_id     TEXT PRIMARY KEY,
  order_ref     TEXT NOT NULL,
  sku           TEXT NOT NULL REFERENCES products(sku),
  customer_name TEXT NOT NULL,
  lat           REAL NOT NULL,
  lng           REAL NOT NULL,
  reason_code   TEXT NOT NULL,              -- size | change_of_mind | defect | wrong_item | damaged | late
  reason_text   TEXT,
  days_since_purchase INTEGER NOT NULL,
  prior_returns INTEGER NOT NULL DEFAULT 0,
  image_path    TEXT,
  created_at    TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'requested',
  -- requested -> analyzed -> atp -> matched -> inspected -> refunded -> resold | returned_to_seller | refurbish | donated | disposed
  nearest_hub   TEXT REFERENCES hubs(hub_id)
);

CREATE TABLE IF NOT EXISTS predictions (
  return_id     TEXT PRIMARY KEY REFERENCES returns(return_id),
  resale_prob   REAL NOT NULL,
  grade         TEXT NOT NULL,              -- A | B | C (불일치면 최대 B)
  verdict       TEXT NOT NULL,              -- 화면 첫 줄 판정 문장
  baseline      REAL NOT NULL,              -- 비슷한 반품 평균(기여도 기준값)
  contributions TEXT NOT NULL,              -- JSON [{key,label,delta_pp,note?}] 기준값+합 = resale_prob
  mismatch      TEXT NOT NULL DEFAULT '[]', -- JSON 사유·상세 사유 불일치 단어
  photo         TEXT,                       -- JSON 사진 품질 {score,sharpness,brightness,contrast} 또는 NULL
  model_version TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
  return_id     TEXT PRIMARY KEY REFERENCES returns(return_id),
  path          TEXT NOT NULL,              -- direct | hub_storage | seller_return | refurbish | donation | disposal
  expected_values TEXT NOT NULL,            -- JSON {path: 원}
  reason        TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

-- ATP(Available-to-Promise) 편입 레코드: 이동 중 재고
CREATE TABLE IF NOT EXISTS atp_inventory (
  return_id     TEXT PRIMARY KEY REFERENCES returns(return_id),
  sku           TEXT NOT NULL,
  hub_id        TEXT NOT NULL REFERENCES hubs(hub_id),
  promise_qty   REAL NOT NULL,              -- = resale_prob (확률적 재고)
  eta_hub       TEXT NOT NULL,              -- 허브 도착 예상 시각
  expires_at    TEXT NOT NULL,              -- 보관 한도
  state         TEXT NOT NULL DEFAULT 'in_transit'  -- in_transit | at_hub | allocated | released
);

CREATE TABLE IF NOT EXISTS matches (
  match_id      TEXT PRIMARY KEY,
  return_id     TEXT NOT NULL REFERENCES returns(return_id),
  order_id      TEXT NOT NULL REFERENCES orders(order_id),
  hub_id        TEXT NOT NULL REFERENCES hubs(hub_id),
  km_customer_hub REAL NOT NULL,
  km_hub_buyer  REAL NOT NULL,
  km_saved      REAL NOT NULL,
  cost_saved    INTEGER NOT NULL,
  co2_saved     REAL NOT NULL,
  solver_run_id TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

-- 검수 이력 체인: 각 이벤트는 직전 해시를 포함 (위변조 검증)
CREATE TABLE IF NOT EXISTS chain_events (
  event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  return_id     TEXT NOT NULL REFERENCES returns(return_id),
  event_type    TEXT NOT NULL,              -- REQUESTED | AI_GRADED | ATP_ENROLLED | MATCHED | INSPECTED | SEALED | REFUNDED | DELIVERED
  payload       TEXT NOT NULL,              -- JSON
  prev_hash     TEXT NOT NULL,
  hash          TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inspections (
  inspection_id TEXT PRIMARY KEY,
  return_id     TEXT NOT NULL REFERENCES returns(return_id),
  hub_id        TEXT NOT NULL REFERENCES hubs(hub_id),
  checklist     TEXT NOT NULL,              -- JSON {exterior, components, weight, tag}
  grade         TEXT NOT NULL,
  qr_token      TEXT NOT NULL UNIQUE,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kpi_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  return_id     TEXT NOT NULL,
  cost_saved    INTEGER NOT NULL,
  km_saved      REAL NOT NULL,
  co2_saved     REAL NOT NULL,
  refund_days_saved REAL NOT NULL,
  resale_days_saved REAL NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_sku_status ON orders(sku, status);
CREATE INDEX IF NOT EXISTS idx_atp_sku_state ON atp_inventory(sku, state);
CREATE INDEX IF NOT EXISTS idx_chain_return ON chain_events(return_id, event_id);
