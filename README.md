# R_ROUTE 결과물 모음

팀 짐덩이들 · 2nd LogisticSolver 2026 (국립창원대학교 스마트물류 문제해결 경진대회)
정리일 2026-11-08

> 반품은 돌아가는 것이 아니라 다시 출발하는 것이다.

## 일정

| 항목 | 기한 | 제출 방법 |
| --- | --- | --- |
| 서류 (보고서 20쪽 이내, 데이터·코드 일체) | 2026-11-13(금) 14:00 | 이메일 |
| 발표자료 (PDF, 표지·목차 포함 15쪽 이내) | 2026-11-20(금) 14:00 | 이메일 |
| 발표심사 (15분, 질의응답 5분 포함) | 2026-11-27(금) | 21호관 226호 |

## 폴더 구성

| 폴더 | 파일 | 용도 |
| --- | --- | --- |
| 01_docs | 01_Strategy_Report_and_Proposal (.pdf / .docx) · 전략 보고서 및 최종 제안서 | 심사위원 관점 검증, 경쟁사 비교, AI 설계, 데이터셋, KPI, 시뮬레이션 결과, 특허성, 발표 15장 설계, 예상 질문 30개, 최종 제안서 본문 |
| 01_docs | 02_MVP_Design_Spec (.pdf / .docx) · MVP 설계서 | UX·User Flow, IA·와이어프레임, 컴포넌트, DB, API, AI 모델, 시스템 아키텍처, 데모 대본, 스토리텔링, 개선·차별화 아이디어 |
| 02_demo | R_ROUTE_Live_Demo.html | 발표 백업용 녹화 데모(본 발표는 04_mvp_code의 실제 MVP로). 브라우저로 열고 "데모 시작" → 스페이스바(→)로 10단계 진행, ←로 이전 |
| 03_simulation | r_route_sim.py, longtail.py, *.csv | 창원시 30일 시뮬레이션(기존 vs R_ROUTE)과 민감도 분석 결과 |
| 04_mvp_code | r_route_mvp/ | 실제로 동작하는 MVP v0.2(신뢰도 개선 반영). FastAPI·OR-Tools·LightGBM 백엔드 + Next.js 프론트엔드. 실행법은 내부 README.md |

## 실행 방법 요약

```bash
# 시뮬레이션 (Python 3.10+, numpy·pandas·scipy)
cd 03_simulation && python r_route_sim.py

# MVP 백엔드
cd 04_mvp_code/r_route_mvp/backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000      # http://localhost:8000/docs
pytest -q                              # 9 passed

# MVP 프론트엔드 (새 터미널)
cd 04_mvp_code/r_route_mvp/frontend
npm install && npm run dev             # http://localhost:3000
```

## 핵심 수치 (창원시 합성 데이터 시뮬레이션)

| 지표 | 기존 방식 | R_ROUTE | 변화 |
| --- | --- | --- | --- |
| 반품 1건 물류비 | 10,559원 | 8,826원 | −16.4% (보수적 시나리오 −9.9%) |
| 재판매 리드타임 (직송가능 반품) | 5.6일 | 3.3일 | −40% |
| 반품 1건 CO₂ | 0.402kg | 0.333kg | −17.2% |
| 직송 매칭률 | — | 74.6% | 직송가능 1,743건 중 1,300건 |

데모 케이스(MVP v0.2 실측): 샘플 사진에 따라 새것 A(약 90%) · 어둡고 흐린 사진 B(약 70%) · 파손 사유 C(약 30%). 반례 시나리오에서 가까운 순서 배정 28,595원 vs 최소비용 흐름 6,794원.

## 제출 전 확인할 것

- 모든 수치는 공개 가정 기반 합성 데이터 결과이며 실제 기업 데이터가 아니다. 제안서·발표에 그대로 명시한다.
- 판매자 창고 위치 가정(수도권 60%)이 절감 효과의 대부분을 만든다. 가정 유지 여부를 팀에서 확정한다.
- 경쟁사 기능, 법령 조문(전자상거래법 제17·18조, 특허법 제30조 등), 데이터셋 라이선스는 웹 검색 없이 작성했다. 공식 출처를 확인하고 출처를 단다.
- 재판매 예측 모델은 약지도 합성 라벨로 학습(AUC 약 0.75)했고, 사진은 품질만 본다(결함 판독은 허브 검수).
- 허브 좌표는 행정동 부근의 가상 위치이며 실제 제휴처가 아니다.

## 온라인 버전 (팀원과 공유하려면 각 페이지의 공유 메뉴에서 권한 부여)

- 전략 보고서: https://claude.ai/artifact/8g1jgokMNZibdTBQ61TWTw
- MVP 설계서: https://claude.ai/artifact/7Zrsx9A7MNfzoTfMTkJwiC
- Live Demo: https://claude.ai/artifact/U7NPPs6kByLtMC9gbsvEA5
