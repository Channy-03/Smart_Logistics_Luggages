# R_ROUTE — 반품을 판매자 창고로 돌려보내지 않는 역물류 엔진

> 2026 국립창원대 스마트물류 문제해결 경진대회 (LogisticSolver 2026) 출품작 · 팀 짐덩이들

반품 요청이 들어오는 순간 그 상품을 **이동 중 재고(ATP)** 로 등록하고, 가까운 동네 거점에서 검수한 뒤 **같은 지역의 다음 구매자에게 바로 보냅니다.** 판매자 창고까지 왕복하던 운송 구간이 사라집니다.

| 지표 (창원시 30일 시뮬레이션, 주문 6만 건·반품 9,015건) | 기존 | R_ROUTE |
|---|---|---|
| 반품 1건당 물류비 | 10,559원 | **8,826원 (−16.4%)** |
| 보수적 가정 (SKU 2만 종, 수요 집중도 낮춤) | | −9.9% |
| 직송 가능 비율 10 / 20 / 30 / 40% | | −8.3 / −16.4 / −24.7 / −32.8% |

※ 모든 수치는 합성 데이터 기반 시뮬레이션 결과이며 실측이 아닙니다. 가정은 [docs/03_assumptions.md](docs/03_assumptions.md)에 있습니다.

---

## 1. 문제 정의

- 온라인 반품은 대부분 `고객 → 판매자 창고 → (검수·재입고) → 새 구매자`로 이동합니다. 같은 동네에 같은 상품을 주문한 사람이 있어도 상품은 수백 km를 왕복합니다.
- 반품이 창고에 도착해 재입고되기 전까지 그 상품은 팔 수 없는 재고로 묶입니다.
- 상세: [docs/01_problem.md](docs/01_problem.md)

## 2. 해결 방법

```
반품 접수 ─▶ AI 재판매 가능성 예측 ─▶ 처리 경로 결정 ─▶ 최소비용 흐름 매칭 ─▶ 거점 검수·QR 봉인 ─▶ 다음 구매자 배송
            (사진 품질·사유·이력)      (6개 경로)          (OR-Tools)          (HMAC + 해시 체인)
```

| 단계 | 하는 일 | 구현 |
|---|---|---|
| 재판매 예측 | 사유·사진 품질·경과일·이력으로 재판매 확률과 A/B/C 등급, 입력별 기여도(%p) 산출 | LightGBM + Platt 보정 + SHAP 기여도 |
| 경로 결정 | 직송 / 거점 보관 / 판매자 반송 / 리퍼 / 기부 / 폐기 중 기대가치가 가장 큰 경로 | 기대가치 식 + 안전 규칙(사유·메모 불일치, 제한 품목) |
| 매칭 | 반품과 신규 주문을 비용 최소로 짝지음. 가까운 순서 배정보다 나은 이유를 반례로 제시 | Min Cost Flow |
| 검수·추적 | 거점 검수 결과를 QR로 봉인, 위조 QR 거부, 이벤트 해시 체인 | HMAC-SHA256, SHA-256 체인 |

## 3. 시스템 구성

```
frontend (Next.js 14) ──REST──▶ backend (FastAPI)
  /analyze  AI 분석                ├─ ml/predictor.py     재판매 예측
  /engine   매칭 엔진              ├─ engine/decision.py  처리 경로
  /map      지도                   ├─ engine/mcf.py       최소비용 흐름
  /verify   거점 검수              ├─ verify.py           QR·해시 체인
  /impact   효과                   └─ SQLite (운영 시 PostgreSQL + PostGIS)
simulation/  창원시 30일 시뮬레이션 (반품률 15%, 거점 10곳)
```

## 4. 기술 스택

| 영역 | 사용 |
|---|---|
| Backend | Python 3.11, FastAPI, SQLite |
| AI | LightGBM, scikit-learn(Platt 보정), Pillow(사진 품질) |
| 최적화 | Google OR-Tools (SimpleMinCostFlow) |
| Frontend | Next.js 14, React 18, Tailwind CSS, Framer Motion, Recharts, React-Leaflet |
| 테스트 | pytest (데모 흐름 + 심사 예상 질문 9개 검증) |

## 5. 실행 방법

```bash
# 백엔드
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                                            # 9 passed
uvicorn app.main:app --port 8000                     # http://localhost:8000/docs

# 프론트엔드 (새 터미널)
cd frontend
npm install
npm run dev                                          # http://localhost:3000
```

인터넷이 없을 때는 `prototype/r_route_demo.html`(녹화된 데모)을 브라우저로 엽니다.

## 6. 폴더 구조

```
.
├── README.md
├── docs/            문제 정의, 설계, 가정, 결과, 역할 분담, 개발 기록
├── backend/         FastAPI 서버, AI 모델, 최적화 엔진, 테스트
├── frontend/        Next.js 데모 화면
├── simulation/      창원시 시뮬레이션 코드와 결과 CSV
├── prototype/       오프라인 백업 데모 (단일 HTML)
├── media/           스크린샷, 시연 영상 링크
└── submission/      제출한 보고서·발표자료 PDF
```

## 7. 개발 과정

| 단계 | 내용 | 확인 방법 |
|---|---|---|
| 1. 문제 정의 | 반품 왕복 구간과 재고 묶임 문제 정리, 기존 서비스 비교 | `docs/01_problem.md` |
| 2. 시뮬레이션 | 창원시 30일 시뮬레이션으로 효과 크기와 민감도 확인 | `simulation/` |
| 3. 설계 | 데이터 모델, API, 처리 경로 6개, 매칭 문제 정식화 | `docs/02_design.md`, `backend/app/schema.sql` |
| 4. 구현 v0.1 | 백엔드 엔진 + 5개 화면 MVP | 태그 `v0.1` |
| 5. 신뢰도 개선 v0.2 | 확률 보정 교체, 사진 점수 재정의, 기여도 설명, 반례 카드 | 태그 `v0.2` |
| 6. 테스트 | 심사 예상 질문을 자동 테스트로 작성 | `backend/tests/test_flow.py` |
| 7. 결과 | 시뮬레이션 + 데모 결과 정리 | `docs/04_results.md` |

자세한 기록과 각 결정의 이유: [docs/DEVLOG.md](docs/DEVLOG.md)

## 8. 한계와 향후 개선

- 재판매 예측은 **합성 라벨**로 학습했습니다(검증 AUC ≈ 0.77). 실제 라벨은 파일럿의 거점 검수 결과로 확보할 계획입니다.
- 사진은 **품질(선명도·밝기·대비)만** 봅니다. 얼룩·찢김 같은 결함은 거점 실물 검수에서 확인합니다. 결함 판독 모델(CLIP 등)은 향후 과제입니다.
- 거리는 직선거리 × 1.3입니다. 운영에서는 실제 도로거리(OSRM)로 바꿉니다.
- 거점 좌표는 행정동 부근의 가상 위치이며 실제 제휴처가 아닙니다.
- 구매자 동의(반품 재유통 상품 수령) 절차와 개인정보 처리 설계가 필요합니다.

## 9. 팀

| 이름 | 역할 |
|---|---|
| 김경진 (팀장) | PM, 문제 정의, 보고서·발표 |
| 김민찬 | 백엔드, AI 모델, 최적화 엔진, 테스트 |
| 전호준 | 프론트엔드, 지도, 데모·시연 영상 |

세부 분담: [docs/ROLES.md](docs/ROLES.md)

## 10. 개발 도구 고지

설계 검토와 코드 작성 일부에 AI 코딩 도구(Claude)를 사용했습니다. 문제 정의, 가정값 선택, 결과 해석과 검증은 팀이 했습니다. 대회 규정상 AI 도구 사용 범위는 주최 측(앵커사업단)에 확인했습니다. <!-- 확인 후 이 문장을 사실대로 고치세요 -->
