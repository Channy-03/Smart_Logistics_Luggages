# 2. 설계

## 처리 흐름

| 단계 | API | 모듈 |
|---|---|---|
| 반품 접수 | `POST /api/returns` | `main.py` |
| AI 분석 | `POST /api/returns/{id}/analyze` | `ml/predictor.py` |
| 경로 결정 | `POST /api/returns/{id}/decide` | `engine/decision.py` |
| 매칭 | `POST /api/match/run?explain&commit` | `engine/mcf.py` |
| 거점 검수·QR | `POST /api/inspections`, `GET /api/verify/{token}` | `verify.py` |
| 배송 완료·KPI | `POST /api/returns/{id}/deliver`, `GET /api/kpi` | `main.py` |
| 반례 | `GET /api/scenario/counterexample` | `main.py`, `engine/mcf.py` |
| 모델 정보 | `GET /api/model` | `ml/predictor.py` |

## 재판매 예측

- 입력: 가격(log), 경과일, 이전 반품 이력, 반품 사유 코드(6), 카테고리(5), 상세 사유 텍스트 점수, 사진 품질 점수
- 모델: LightGBM → Platt 보정 → 확률. 등급 A ≥ 0.8, B ≥ 0.6, 그 외 C
- 설명: LightGBM `pred_contrib`(SHAP)를 입력 그룹(사유·사진·경과일·이력·상품)으로 묶어 %p로 표시. 기준값 + 기여도 합 = 최종값
- 안전 규칙: 사유 코드와 상세 사유가 충돌하면 등급 상한 B, 직송 차단. 불량·파손 사유는 사진 기여도를 0 이하로 제한

## 처리 경로 결정

경로 k의 기대가치

```
V_k = p·R_k·가격 − (1−p)·F_k − 운송비 − 검수비 − 가격·δ·t − λ·탄소 + 신규 출고 회피 효과
```

직송, 거점 보관, 판매자 반송, 리퍼, 기부, 폐기 중 V_k가 가장 큰 경로를 고릅니다. 제한 품목(화장품 등)은 직송·거점 보관을 막습니다.

## 매칭: 최소비용 흐름

- 노드: 반품(공급 +1), 신규 재고(공급 +|주문|), 주문(수요 −1), 판매자 창고(수요 −|반품|)
- 간선: 반품→주문(같은 SKU, 구매자 동의, 25km 이내), 반품→판매자, 신규 재고→주문, 신규 재고→판매자(비용 0)
- 비교 기준: 반품이 들어온 순서대로 가장 가까운 주문에 배정(greedy). 반례에서 greedy 28,595원 / 603km, MCF 6,794원 / 27km

## 검수·추적

- 거점 검수 결과를 HMAC-SHA256으로 서명한 QR 토큰으로 봉인. 토큰이 바뀌면 검증 거부
- 상태 변화를 SHA-256 해시 체인 이벤트로 기록

## 데이터 모델

`backend/app/schema.sql`: hubs, products, orders, returns, predictions, decisions, atp_inventory, matches, inspections, chain_events, kpi_events
