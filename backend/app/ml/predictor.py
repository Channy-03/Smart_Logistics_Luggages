"""재판매 가능성 예측 (AI Prediction Layer) · v0.2

구조
  입력 3종 -> LightGBM(결합) -> Platt 보정 -> 재판매 가능성 p, 등급 A/B/C
  - 반품 사유 : 사유 코드 + 상세 사유 텍스트(한국어 키워드 점수. KR-SBERT로 교체 가능)
  - 사진 품질 : 밝기·선명도(라플라시안 분산)·대비. '결함 판독'이 아니라 '사진이 판단에 쓸 만한가'를 본다.
                사진이 없으면 결측(NaN)으로 두고 LightGBM이 결측 경로로 처리한다.
  - 구매 정보 : 경과일, 고객 반품 이력, 가격, 카테고리
설명
  - 기여도: LightGBM pred_contrib(SHAP)를 입력 그룹별로 묶고, 정해진 순서로 누적해 %p로 환산한다.
    기준값(비슷한 반품 평균) + 각 기여 = 최종값 이 항상 정확히 맞는다.
  - 불일치: 사유 코드는 '사이즈/변심'인데 상세 사유에 결함 단어가 있으면 경고하고 등급을 B 이하로 제한한다.
학습 데이터
  공개 데이터에 '재판매 성공' 라벨이 없어 약지도 합성 라벨 6,000건으로 학습한다(검증 20%).
  파일럿에서는 허브 검수 결과가 실제 라벨이 된다.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

MODEL_VERSION = "rroute-fusion-0.2"
REASONS = ["size", "change_of_mind", "late", "wrong_item", "defect", "damaged"]
REASON_KO = {"size": "사이즈", "change_of_mind": "단순 변심", "late": "배송 지연", "wrong_item": "오배송",
             "defect": "상품 불량", "damaged": "파손·오염"}
CATS = ["fashion", "electronics", "living", "beauty", "food"]
GOOD_REASONS = {"size", "change_of_mind", "late", "wrong_item"}

POS = ["사이즈", "작아", "커요", "커서", "색상", "단순", "변심", "마음", "미개봉", "새상품", "착용 안", "포장 그대로", "한 번도"]
NEG = ["찢", "파손", "깨", "얼룩", "오염", "냄새", "고장", "불량", "작동 안", "흠집", "스크래치", "누락", "사용감", "변색", "구멍"]

# 피처 순서와 설명 그룹
FEATS = ["log_price", "days", "prior"] + [f"r_{r}" for r in REASONS] + [f"c_{c}" for c in CATS] + ["text", "quality"]
GROUPS = [  # (key, 라벨, 피처 이름 목록) - 누적 순서 = 화면 표시 순서
    ("reason", "반품 사유", [f"r_{r}" for r in REASONS] + ["text"]),
    ("photo", "사진 품질", ["quality"]),
    ("days", "구매 후 경과일", ["days"]),
    ("history", "고객 반품 이력", ["prior"]),
    ("product", "상품 가격·카테고리", ["log_price"] + [f"c_{c}" for c in CATS]),
]

MODEL_CARD = {
    "version": MODEL_VERSION,
    "inputs": ["반품 사유(코드+텍스트)", "사진 품질(밝기·선명도·대비)", "구매 정보(경과일·반품 이력·가격·카테고리)"],
    "fusion": "LightGBM 이진 분류 + Platt 보정",
    "training_data": "공개 데이터(UCI Online Retail II 반품률·경과일, Olist 주문 분포, KOSIS 상품군 비중)의 분포로 만든 약지도 합성 라벨 6,000건",
    "limitations": [
        "사진에서 얼룩·찢김 같은 결함은 아직 판독하지 않는다(사진 품질만 본다). 결함은 허브 실물 검수에서 확인한다.",
        "합성 라벨로 학습해 확률 값 자체는 실제 재판매율과 다를 수 있다.",
        "반품 사유 텍스트는 키워드 규칙으로 읽는다(KR-SBERT로 교체 예정).",
    ],
    "pilot_plan": "허브 검수 등급을 정답 라벨로 모아 매주 재학습한다. 고객사 1곳(월 반품 약 9천 건, 직송가능 20%) 기준 3개월에 약 5,400건.",
}


def text_score(reason_code: str, reason_text: str | None) -> float:
    base = {"size": 0.88, "change_of_mind": 0.84, "late": 0.82, "wrong_item": 0.75, "defect": 0.25, "damaged": 0.15}[reason_code]
    t = reason_text or ""
    s = base + 0.03 * sum(k in t for k in POS) - 0.18 * sum(k in t for k in NEG)
    return float(min(0.98, max(0.02, s)))


def find_mismatch(reason_code: str, reason_text: str | None) -> list[str]:
    """사유 코드가 '문제없는 반품'인데 상세 사유에 결함 단어가 있으면 그 단어들을 돌려준다."""
    if reason_code not in GOOD_REASONS:
        return []
    t = reason_text or ""
    return [k for k in NEG if k in t]


def photo_quality(image_bytes: bytes | None) -> dict | None:
    """사진 품질 점수(0~1)와 세부 항목. 결함 판독이 아니다. 사진이 없거나 읽을 수 없으면 None."""
    if not image_bytes:
        return None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(image_bytes)).convert("L")
        im.thumbnail((320, 320))
        a = np.asarray(im, dtype=np.float32)
        lap = 4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
        sharp = float(min(1.0, lap.var() / 400.0))
        m = float(a.mean())  # 제품 사진은 흰 배경이 많아 밝은 쪽은 관대하게, 어둡거나 하얗게 날아간 사진만 감점
        bright = float(max(0.0, min(1.0, (m - 40) / 90) - max(0.0, (m - 238) / 15)))
        contrast = float(min(1.0, a.std() / 55.0))
        score = 0.45 * sharp + 0.35 * bright + 0.20 * contrast
        return {"score": round(score, 3), "sharpness": round(sharp, 2), "brightness": round(bright, 2),
                "contrast": round(contrast, 2)}
    except Exception:
        return None


def _features(reason_code, category, price, days, prior, ts, quality):
    f = np.zeros(len(FEATS))
    f[0], f[1], f[2] = math.log(price), days, prior
    f[3 + REASONS.index(reason_code)] = 1
    f[3 + len(REASONS) + CATS.index(category)] = 1
    f[-2] = ts
    f[-1] = np.nan if quality is None else quality
    return f


def _synthetic(n=6000, seed=0):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        rc = rng.choice(REASONS, p=[.32, .25, .08, .1, .15, .1])
        cat = rng.choice(CATS, p=[.4, .15, .25, .12, .08])
        price = float(rng.lognormal(math.log(50000), .6))
        days = int(rng.integers(0, 15))
        prior = int(rng.poisson(.6))
        ts = float(np.clip(text_score(rc, None) + rng.normal(0, .06), 0, 1))
        q = None if rng.random() < .25 else float(np.clip(rng.normal(.72, .15), 0, 1))
        # 사진이 나쁘면 상태 확인이 어려워 재판매 가능성이 낮아진다는 가정(사진 없음은 중립보다 약간 낮게)
        # 사유가 불량·파손이면 선명한 사진은 결함을 확인해 줄 뿐이므로 재판매 가능성을 올리지 않는다
        if rc in ("defect", "damaged"):
            q_eff = -.1 if q is None else -.3 * max(0.0, q - .6)
        else:
            q_eff = -.35 if q is None else 3.6 * (q - .6)
        logit = .35 + 3.2 * (ts - .55) + q_eff - .08 * days - .4 * prior \
            - (1.0 if cat in ("beauty", "food") else 0) - (.3 if cat == "electronics" else 0)
        y.append(rng.random() < 1 / (1 + math.exp(-logit)))
        X.append(_features(rc, cat, price, days, prior, ts, q))
    return np.array(X), np.array(y, int)


@dataclass
class Prediction:
    resale_prob: float
    grade: str
    grade_label: str
    verdict: str
    baseline: float
    contributions: list = field(default_factory=list)
    mismatch: list = field(default_factory=list)
    photo: dict | None = None
    text_score: float = 0.0
    model_version: str = MODEL_VERSION


class Predictor:
    def __init__(self):
        import lightgbm as lgb
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import brier_score_loss, roc_auc_score
        X, y = _synthetic()
        cut = int(len(X) * .8)
        params = dict(objective="binary", learning_rate=.05, num_leaves=15, min_data_in_leaf=40, verbose=-1, seed=0)
        self.booster = lgb.train(params, lgb.Dataset(X[:cut], y[:cut], feature_name=FEATS), num_boost_round=200)
        raw = self.booster.predict(X[cut:], raw_score=True)
        lr = LogisticRegression().fit(raw.reshape(-1, 1), y[cut:])   # Platt 보정: p = sigmoid(a*z + b)
        self.a, self.b = float(lr.coef_[0, 0]), float(lr.intercept_[0])
        cal = self._cal(raw)
        self.metrics = {"auc": round(float(roc_auc_score(y[cut:], cal)), 3),
                        "brier": round(float(brier_score_loss(y[cut:], cal)), 3),
                        "n_train": cut, "n_valid": len(X) - cut,
                        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.idx = {f: i for i, f in enumerate(FEATS)}

    def _cal(self, z):
        return 1 / (1 + np.exp(-(self.a * np.asarray(z) + self.b)))

    def _explain(self, x, cap_photo=False):
        """기여도 분해. cap_photo=True면 사진 기여(로그오즈)를 0 이하로 제한한다(사진이 가능성을 올리지 못하게)."""
        contrib = self.booster.predict(x[None], pred_contrib=True)[0]   # 피처별 기여(로그오즈) + 마지막 = 기준값
        z = float(contrib[-1])
        base = float(self._cal(z))
        steps, prev, capped = [], base, False
        for key, label, feats in GROUPS:
            dz = float(sum(contrib[self.idx[f]] for f in feats))
            if cap_photo and key == "photo" and dz > 0:
                dz, capped = 0.0, True
            z += dz
            cur = float(self._cal(z))
            steps.append({"key": key, "label": label, "delta_pp": round((cur - prev) * 100, 1)})
            prev = cur
        return prev, base, steps, capped

    def predict(self, reason_code, reason_text, category, price, days, prior, image_bytes=None) -> Prediction:
        ts = text_score(reason_code, reason_text)
        ph = photo_quality(image_bytes)
        # 불량·파손 사유에서는 선명한 사진이 결함을 확인해 줄 뿐이므로 사진이 가능성을 올리지 못하게 한다
        p, base, steps, photo_capped = self._explain(
            _features(reason_code, category, price, days, prior, ts, None if ph is None else ph["score"]),
            cap_photo=reason_code in ("defect", "damaged"))
        mism = find_mismatch(reason_code, reason_text)
        grade, label = ("A", "Like New") if p >= .8 else (("B", "Good") if p >= .6 else ("C", "Needs Review"))
        if mism and grade == "A":
            grade, label = "B", "Good"
        verdict = {
            "A": "다음 구매자에게 바로 보낼 수 있어요",
            "B": "가까운 허브에서 확인한 뒤 다시 판매해요",
            "C": "판매자가 직접 확인해야 해요. 판매자 창고로 보낼게요",
        }[grade]
        if mism:
            verdict = f"반품 사유는 '{REASON_KO[reason_code]}'지만 상세 사유에 '{mism[0]}'이(가) 있어요. 바로 보내지 않고 허브에서 확인할게요"
        # 사진 기여 설명 문구
        photo_step = next(s for s in steps if s["key"] == "photo")
        if ph is None:
            photo_step["note"] = "사진이 없어 사진 품질은 반영하지 않았어요"
        elif photo_capped:
            photo_step["note"] = "반품 사유가 불량·파손이라 사진이 선명해도 가능성을 올리지 않아요"
        elif abs(photo_step["delta_pp"]) < 1:
            photo_step["note"] = "사진은 판단에 쓸 만했지만 결과를 크게 바꾸지 않았어요"
        elif photo_step["delta_pp"] > 0:
            photo_step["note"] = "사진이 밝고 선명해 상태를 판단하기 좋았어요"
        else:
            photo_step["note"] = "사진이 어둡거나 흐려 판단 근거가 약해졌어요"
        return Prediction(round(p, 4), grade, label, verdict, round(base, 4), steps, mism, ph, round(ts, 3))


_P: Predictor | None = None


def get_predictor() -> Predictor:
    global _P
    if _P is None:
        _P = Predictor()
    return _P
