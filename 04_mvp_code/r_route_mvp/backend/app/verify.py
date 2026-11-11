"""Verification Hub: 해시 체인 이력 + HMAC 서명 QR 토큰"""
import base64
import hashlib
import hmac
import json
import os

from .db import dumps, now, rows

SECRET = os.environ.get("RROUTE_QR_SECRET", "dev-only-change-me").encode()
GENESIS = "0" * 64


def append_event(c, return_id: str, event_type: str, payload: dict) -> str:
    last = c.execute("SELECT hash FROM chain_events WHERE return_id=? ORDER BY event_id DESC LIMIT 1", (return_id,)).fetchone()
    prev = last["hash"] if last else GENESIS
    ts = now()
    body = dumps({"return_id": return_id, "type": event_type, "payload": payload, "ts": ts})
    h = hashlib.sha256((prev + body).encode()).hexdigest()
    c.execute("INSERT INTO chain_events (return_id, event_type, payload, prev_hash, hash, created_at) VALUES (?,?,?,?,?,?)",
              (return_id, event_type, dumps(payload), prev, h, ts))
    return h


def verify_chain(c, return_id: str):
    ev = rows(c, "SELECT * FROM chain_events WHERE return_id=? ORDER BY event_id", (return_id,))
    prev, ok = GENESIS, True
    for e in ev:
        body = dumps({"return_id": return_id, "type": e["event_type"], "payload": json.loads(e["payload"]), "ts": e["created_at"]})
        ok = ok and e["prev_hash"] == prev and hashlib.sha256((prev + body).encode()).hexdigest() == e["hash"]
        prev = e["hash"]
    return ok, ev


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def sign_token(claims: dict) -> str:
    body = _b64(dumps(claims).encode())
    sig = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest()[:16])
    return f"{body}.{sig}"


def read_token(token: str):
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest()[:16])
        if not hmac.compare_digest(good, sig):
            return None
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return None
