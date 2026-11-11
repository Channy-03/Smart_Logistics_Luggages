import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get("RROUTE_DB", str(Path(__file__).resolve().parent.parent / "rroute.db"))
SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db(reset: bool = False) -> None:
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    with conn() as c:
        c.executescript(SCHEMA)


def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(c, sql, args=()):
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
