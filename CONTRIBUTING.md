# 협업 규칙

팀 짐덩이들(김경진·김민찬·전호준)이 이 저장소에서 함께 작업하는 방법입니다. 역할 분담은 [docs/ROLES.md](docs/ROLES.md)에 있습니다.

## 1. main에는 직접 push하지 않는다

- `main`은 **항상 실행되는 상태**를 유지합니다. 제출(11/13)과 발표(11/27) 때 쓰는 버전입니다.
- 모든 변경은 **브랜치 → Pull Request(PR) → 리뷰·승인 → Merge** 순서로 main에 들어갑니다.
- 예외는 저장소를 처음 만들 때 올린 초기 커밋뿐입니다.

## 2. 브랜치

- main에서 새 브랜치를 만들어 작업합니다.
- 이름은 `종류/내용` 또는 `dev-이름` 형식으로 짓습니다.

| 종류 | 예시 |
|---|---|
| 기능 추가 | `feat/frontend-hojun`, `feat/backend-clip` |
| 버그 수정 | `fix/predictor-threshold` |
| 문서 | `docs/problem-results-kyungjin` |
| 개인 작업 브랜치 | `dev-minchan` |

- Merge한 뒤에도 같은 브랜치를 계속 쓴다면, 다음 작업 전에 main을 먼저 받아 옵니다(`git pull origin main`).

## 3. 커밋

- **본인 계정으로, 본인이 한 작업만** 커밋합니다. 다른 사람 이름으로 커밋하거나 날짜를 바꾸지 않습니다.
- 메시지는 `종류: 무엇을 했는지` 형식으로 씁니다. 예: `backend: 파손 사유일 때 사진 기여도 0으로 제한`
- 종류: `backend`, `frontend`, `sim`, `test`, `docs`, `prototype`, `media`, `fix`, `chore`

## 4. Pull Request와 리뷰

- PR을 열 때 템플릿(무엇을·왜·확인 방법)을 채웁니다.
- **작성자가 아닌 팀원 1명 이상이 Approve**해야 Merge할 수 있습니다. 본인 PR은 본인이 승인하지 않습니다.
- 리뷰어는 **Files changed** 탭에서 줄 단위로 코멘트를 남기고, 확인이 끝나면 **Review changes → Approve**를 누릅니다.
- 코멘트(대화)가 모두 해결(Resolve)되어야 Merge할 수 있습니다.
- 승인 뒤에 새 커밋을 올리면 승인이 풀리므로 다시 리뷰를 받습니다.
- 급할 때는 단톡방에 PR 링크를 올려 바로 리뷰를 요청합니다.

## 5. 다른 사람 파트를 고칠 때

- 누구나 고칠 수 있지만, **그 파트 담당자가 리뷰어**가 됩니다.
  - `backend/`, `simulation/` → 김민찬
  - `frontend/`, `prototype/`, `media/` → 전호준
  - `docs/01_problem.md`, `docs/04_results.md`, `submission/` → 김경진
- 담당자가 확인하지 않은 변경은 발표 Q&A에서 설명할 수 없으므로 Merge하지 않습니다.

## 6. Merge 전 확인

- 백엔드 변경: `cd backend && python -m pytest -q`가 모두 통과해야 합니다.
- 프론트엔드 변경: `cd frontend && npm run build`가 통과해야 합니다.
- 숫자를 바꾼 경우: README 표, `docs/04_results.md`, 보고서의 숫자가 서로 맞는지 확인합니다.

## 7. 태그

- 제출 시점의 main에 태그를 붙입니다: `v0.2`(3개 파트 통합), `v0.2-submission`(11/13 서류 제출).

## 8. GitHub 설정 (저장소 관리자)

Settings → Rules → Rulesets에서 `main`에 다음 규칙을 켭니다.

- Restrict deletions
- Require a pull request before merging: 승인 1명, 새 커밋 시 승인 해제, 대화 해결 필수
- Block force pushes
- Bypass list는 비워 둡니다.
