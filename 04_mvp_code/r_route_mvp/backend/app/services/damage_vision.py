"""Gemini Vision integration for return-product damage assessment."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx

# .env 파일이 있으면 자동으로 로드
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    pass


DAMAGE_SYSTEM_PROMPT = """당신은 반품 물류센터의 상품 외관 검수 AI입니다.
입력 이미지에서 보이는 상품의 손상만 평가하세요. 이미지가 어둡거나, 흐리거나,
상품이 충분히 보이지 않으면 추측하지 말고 needs_manual_review를 true로 설정하세요.

등급 기준:
- S: 새상품 수준. 사용 흔적, 오염, 스크래치, 찌그러짐, 파손이 보이지 않음.
- A: 미세 흠집 또는 매우 경미한 사용 흔적만 보이며, 정상 재판매 가능.
- B: 눈에 띄는 오염, 깊은 스크래치, 찌그러짐, 균열, 찢김 또는 부품 손상.
- C: 기능/안전에 영향을 줄 수 있는 심각한 파손, 큰 균열·찢김, 누수, 분해,
  광범위한 오염 또는 재판매가 불가능한 상태.

반드시 아래 JSON 객체만 반환하세요. Markdown, 코드 펜스, 설명 문장은 절대 추가하지 마세요.
{
  "grade": "S | A | B | C",
  "damage_summary": "한국어 한 문장",
  "visible_evidence": ["이미지에서 확인한 근거"],
  "confidence": 0.0,
  "needs_manual_review": false
}
confidence는 0.0~1.0 숫자입니다. 이미지 품질이 낮거나 판단이 불확실하면
needs_manual_review를 true로 하고 visible_evidence에 이유를 적으세요."""

DAMAGE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "grade": {"type": "STRING", "enum": ["S", "A", "B", "C"]},
        "damage_summary": {"type": "STRING"},
        "visible_evidence": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": {"type": "NUMBER"},
        "needs_manual_review": {"type": "BOOLEAN"},
    },
    "required": ["grade", "damage_summary", "visible_evidence", "confidence", "needs_manual_review"],
}

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemini-pro-latest",
]

API_HOST = "generativelanguage.googleapis.com"


class VisionServiceError(RuntimeError):
    """A safe error that can be shown by the API without provider internals."""


def _build_url(path: str) -> str:
    return "https" + "://" + API_HOST + path


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _extract_json(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(_clean_json_text(text))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise VisionServiceError("Vision API returned an invalid JSON response.") from exc

    if not isinstance(result, dict) or result.get("grade") not in {"S", "A", "B", "C"}:
        raise VisionServiceError("Vision API returned an invalid damage grade.")
    if not isinstance(result.get("visible_evidence"), list):
        raise VisionServiceError("Vision API returned invalid evidence.")
    try:
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise VisionServiceError("Vision API returned invalid confidence.") from exc
    result["damage_summary"] = str(result.get("damage_summary", ""))
    result["visible_evidence"] = [str(item) for item in result["visible_evidence"]]
    result["needs_manual_review"] = bool(result.get("needs_manual_review", False))
    return result


async def _discover_available_models(client: httpx.AsyncClient, api_key: str) -> list[str]:
    try:
        resp = await client.get(
            _build_url("/v1beta/models"),
            params={"key": api_key},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        available: list[str] = []
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            name = m.get("name", "")
            if "generateContent" in methods and name.startswith("models/gemini"):
                short_name = name.replace("models/", "", 1)
                if "embedding" not in short_name and "tts" not in short_name:
                    available.append(short_name)
        available.sort(key=lambda x: (0 if "flash" in x else 1, x))
        return available
    except Exception:
        return []


async def assess_damage(image: bytes, mime_type: str) -> dict[str, Any]:
    """Call Gemini with an image and return a validated, JSON-only assessment."""
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise VisionServiceError("GEMINI_API_KEY is not configured on the server.")

    env_model = (os.getenv("GEMINI_VISION_MODEL") or "").strip().strip('"').strip("'")
    if env_model.startswith("models/"):
        env_model = env_model.replace("models/", "", 1)

    candidates: list[str] = []
    if env_model:
        candidates.append(env_model)
    for m in FALLBACK_MODELS:
        if m not in candidates:
            candidates.append(m)

    request_body = {
        "systemInstruction": {"parts": [{"text": DAMAGE_SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [
            {"text": "이 반품 상품 사진의 손상 등급을 판독하세요."},
            {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(image).decode("ascii")}},
        ]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": DAMAGE_RESPONSE_SCHEMA,
        },
    }

    last_status = None
    last_detail = ""

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            for model_name in candidates:
                url = _build_url(f"/v1beta/models/{model_name}:generateContent")
                response = await client.post(url, params={"key": api_key}, json=request_body)
                if response.status_code == 200:
                    return _extract_json(response.json())

                last_status = response.status_code
                try:
                    last_detail = response.json().get("error", {}).get("message", response.text[:200])
                except Exception:
                    last_detail = response.text[:200]

                if response.status_code != 404:
                    break

            if last_status == 404:
                discovered = await _discover_available_models(client, api_key)
                for model_name in discovered:
                    if model_name in candidates:
                        continue
                    url = _build_url(f"/v1beta/models/{model_name}:generateContent")
                    response = await client.post(url, params={"key": api_key}, json=request_body)
                    if response.status_code == 200:
                        return _extract_json(response.json())
                    last_status = response.status_code
                    try:
                        last_detail = response.json().get("error", {}).get("message", response.text[:200])
                    except Exception:
                        last_detail = response.text[:200]
                    if response.status_code != 404:
                        break

    except httpx.HTTPError as exc:
        raise VisionServiceError(f"Gemini Vision network error: {exc}") from exc

    raise VisionServiceError(f"Gemini Vision request failed ({last_status}): {last_detail}")