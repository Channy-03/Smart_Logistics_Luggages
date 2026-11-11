# R_ROUTE MVP

반품 접수 순간 상품을 이동 중 재고(ATP)로 편입하고, 같은 지역 신규 주문에 재할당하는 역물류 엔진.

```
backend/   FastAPI · OR-Tools Min Cost Flow · LightGBM · SQLite(운영: PostgreSQL+PostGIS)
frontend/  Next.js 14 · Tailwind(shadcn 패턴) · Framer Motion · Recharts · React-Leaflet
```

## 실제 사진 손상 판독 (Gemini Vision)

`/vision`에서 반품 사진(JPEG/PNG/WebP, 최대 10MB)을 올리면 `S(새상품)`,
`A(미세 흠집)`, `B(눈에 띄는 파손)`, `C(재판매 불가)` 등급을 반환한다.

```bash
# backend/.env.example을 참고해 배포 환경 또는 현재 셸에 설정
GEMINI_API_KEY=...                 # Windows PowerShell: $env:GEMINI_API_KEY="..."
# 선택: GEMINI_VISION_MODEL=gemini-2.5-flash
```

- `POST /api/vision/damage-assessment`는 `multipart/form-data`의 `image` 필드를 받는다.
- 프롬프트와 Gemini JSON Schema가 JSON 객체만 허용하고, 서버가 등급·신뢰도·근거 형식을 다시 검증한다.
- Vision 결과는 보조 판독이며, 불확실한 사진은 `needs_manual_review: true`로 허브 실물 검수를 요청한다.

## 로컬 실행 방법 (Windows PowerShell)

사전 준비: Python 3.10 이상과 Node.js 18 이상을 설치한다. 아래의 백엔드와 프런트엔드는 **서로 다른 PowerShell 창**에서 실행한다.

### 1. 백엔드 실행

프로젝트 루트에서 다음을 실행한다.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Vision 판독 화면을 사용할 때만 설정한다. 실제 키는 Git에 저장하지 않는다.
$env:GEMINI_API_KEY = "발급받은_Gemini_API_키"
# 선택: $env:GEMINI_VISION_MODEL = "gemini-2.5-flash"

uvicorn app.main:app --reload --port 8000
```

- API 문서: <http://localhost:8000/docs>
- 상태 확인: <http://localhost:8000/api/health>
- 가상환경 활성화가 실행 정책 때문에 막히면, 활성화 없이 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`처럼 가상환경 Python을 직접 실행할 수 있다.
- Vision API 키 없이도 기존 데모 기능은 실행되지만, `/vision`의 실제 사진 판독 요청은 설정 오류를 반환한다.

### 2. 프런트엔드 실행

새 PowerShell 창에서 프로젝트 루트로 이동한 후 실행한다.

```powershell
cd frontend
npm install

# 기본값은 http://localhost:8000 이므로 같은 PC에서 백엔드를 실행했다면 생략 가능
# $env:RROUTE_API = "http://localhost:8000"

npm run dev
```

브라우저에서 <http://localhost:3000>을 열고, 실제 사진 판독은 상단 메뉴의 **Vision 판독** 또는 <http://localhost:3000/vision>에서 실행한다. 배포 전 확인은 `npm run build`로 할 수 있다.

### 3. 테스트 (선택)

백엔드 가상환경이 활성화된 창에서 실행한다.

```powershell
pytest -q
```

서버를 켤 때마다 창원시 데모 월드(허브 10곳, 주문 39건, 배경 반품 6건)가 새로 시드된다. `POST /api/demo/reset`으로 언제든 초기화.

## 데모 순서 (5분 발표용)

0. 상단 **데모 초기화**를 눌러 시드 데이터와 분석 기록을 처음 상태로 되돌린다.
1. **AI 분석** `/analyze` → 샘플 **파손 사유** 실행(C등급, 직송 차단) → **새것 사진** 실행(A등급) → 기여도 막대로 "왜 이 값인지" 설명
2. 같은 화면에서 **어둡고 흐린 사진** 실행 → "이전 분석과 비교"에서 사진 품질 기여가 +에서 −로 바뀌는 것을 보여준다
3. **사유·메모 불일치** 실행 → 경고, 직송 차단. "이 분석은 어떻게 만들어지나요?"로 모델 정보 패널을 연다
4. **새것 사진**을 다시 실행 → **최적 구매자 찾기** → `/engine`에서 최적화 실행(dry-run) → 아래 반례 카드(가까운 순서 28,595원 vs 최소비용 흐름 6,794원) → **매칭 확정**
5. **Live Map** `/map` "내 반품" 화면 → **Hub 검수** `/verify` 봉인 → **Impact** `/impact`

## v0.2 변경 사항 (발표 신뢰도 개선)

- 확률 보정을 Isotonic(계단형, 0.95에서 막힘)에서 Platt(연속)으로 교체
- 이미지 점수를 "사진 품질 점수"(선명도·밝기·대비)로 재정의. 윤곽선이 많다고 점수가 오르지 않게 했다. 결함 판독은 하지 않는다고 화면과 모델 카드에 명시
- `pred_contrib`(SHAP) 기반 기여도: 비슷한 반품 평균 + 입력별 %p = 최종값
- 반품 사유 코드와 상세 사유가 충돌하면 경고하고 직송을 막는 규칙
- `GET /api/model` 모델 정보, `GET /api/scenario/counterexample` 반례, 매칭 결과에 `greedy_cost`(가까운 순서 배정 비용) 추가
- 프론트: 샘플 사진 4종, 판정 우선 결과 카드, 이전 분석 비교, 모델 정보 패널, 지도 "내 반품" 모드, 데모 초기화 버튼
- 삭제: 스캔 애니메이션, 서브모델 점수 막대, 발표 중 시뮬레이션 재실행 버튼

## 모델과 데이터에 대한 정직한 고지

- 재판매 예측 모델은 **약지도 합성 라벨**로 학습한다(검증 AUC ≈ 0.75). 실제 라벨은 파일럿의 허브 검수 결과로 확보한다.
- 사진은 **품질(선명도·밝기·대비)만** 본다. 얼룩·찢김 같은 결함은 허브 실물 검수에서 확인한다.
- 반품 사유 텍스트는 키워드 규칙으로 읽는다. KR-SBERT로 교체할 수 있는 구조다.
- 거리는 직선거리 × 1.3. 운영에서는 OSRM 도로거리 행렬로 교체한다.
- 허브 좌표는 행정동 부근의 가상 위치이며 실제 제휴처가 아니다.
