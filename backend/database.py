import json
import sqlite3
import time
from contextlib import contextmanager, closing
from . import config
from .services.report_outcome import outcome_report


@contextmanager
def connection():
    config.DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(config.DB, timeout=10)) as db, db:
        yield db


def init():
    with connection() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, at REAL, claim TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS cache(id TEXT PRIMARY KEY, at REAL, body TEXT);
        CREATE TABLE IF NOT EXISTS experiments(id INTEGER PRIMARY KEY, at REAL, body TEXT);
        """)


def cache_get(key):
    with connection() as db:
        row = db.execute(
            "SELECT body FROM cache WHERE id=? AND at>?", (key, time.time() - 86400)
        ).fetchone()
    return json.loads(row[0]) if row else None


def cache_put(key, items):
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO cache VALUES(?,?,?)",
            (key, time.time(), json.dumps(items)),
        )


def save(report):
    with connection() as db:
        db.execute(
            "INSERT INTO reports VALUES(?,?,?,?)",
            (report["id"], time.time(), report["claim"], json.dumps(report)),
        )


def report(key):
    with connection() as db:
        row = db.execute("SELECT body FROM reports WHERE id=?", (key,)).fetchone()
    return outcome_report(json.loads(row[0])) if row else None


def history(query):
    with connection() as db:
        rows = db.execute(
            "SELECT id,claim,json_extract(body,'$.verdict'),json_extract(body,'$.date'), CASE WHEN json_extract(body,'$.verdict') = 'UNVERIFIABLE' THEN body END FROM reports WHERE instr(lower(claim),lower(?))>0 ORDER BY at DESC LIMIT 100",
            (query,),
        ).fetchall()
    return [
        dict(
            id=key,
            claim=claim,
            verdict=outcome_report(json.loads(old))["verdict"] if old else verdict,
            date=date,
        )
        for key, claim, verdict, date, old in rows
    ]


def experiment(result):
    with connection() as db:
        db.execute(
            "INSERT INTO experiments(at,body) VALUES(?,?)",
            (time.time(), json.dumps(result)),
        )
