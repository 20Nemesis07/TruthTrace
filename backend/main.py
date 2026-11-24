import asyncio
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from . import database
from .config import provider, ROOT
from .schemas import Claim, Validate
from .services.claim_processor import analyze
from .services.evidence_retriever import retrieve
from .services.evidence_ranker import rank
from .services.evidence_validator import validate
from .services.pipeline import verify
from evaluation.evaluate_prompts import run_evaluation

jobs = {}
tasks = set()
requests_by_ip = defaultdict(deque)


@asynccontextmanager
async def lifespan(app):
    database.init()
    yield
    for task in list(tasks):
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="TruthTrace", version="2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def limits(req: Request, call_next):
    if req.method == "POST":
        now = time.monotonic()
        key = (req.client.host, req.url.path == "/api/evaluate")
        times = requests_by_ip[key]
        while times and times[0] < now - 60:
            times.popleft()
        if len(times) >= (1 if key[1] else 20):
            return JSONResponse(
                {"detail": "Request limit reached. Retry in one minute."}, 429
            )
        times.append(now)
    return await call_next(req)


@app.get("/api/health")
def health():
    n, m, k = provider()
    return {"status": "ok", "provider": n, "model": m, "key_configured": bool(k)}


@app.post("/api/claims/analyze")
async def analyze_route(c: Claim):
    a, w = await analyze(c.claim, not c.offline and bool(provider()[2]))
    return {"analysis": a, "limitations": w}


@app.post("/api/evidence/search")
async def search(c: Claim):
    a, w = await analyze(c.claim, not c.offline and bool(provider()[2]))
    docs, notes = await retrieve(a, c.offline)
    return {"queries": a.queries, "evidence": rank(docs, a), "limitations": w + notes}


@app.post("/api/evidence/validate")
def validation(c: Validate):
    r = detail(c.report_id)
    v, e = validate(c.findings, r["evidence"], r["analysis"]["assertions"])
    return {"valid": v, "failures": e}


@app.get("/api/history")
def history(q: str = Query("", max_length=200)):
    return database.history(q)


@app.get("/api/history/{key}")
def detail(key: str):
    r = database.report(key)
    if r is None:
        raise HTTPException(404, "Unknown verification")
    return r


@app.post("/api/verify")
async def verify_route(c: Claim, background: bool = False):
    if not background:
        return await verify(c)
    for k in list(jobs):
        if time.monotonic() - jobs[k]["start"] > 900:
            jobs.pop(k)
    if len(tasks) >= 6:
        raise HTTPException(429, "Verification queue is busy.")
    key = uuid.uuid4().hex
    job = jobs[key] = {"start": time.monotonic(), "stage": "Queued", "done": False}

    async def work():
        try:
            result = await verify(c, lambda s: job.update(stage=s))
            job.update(report_id=result["id"])
        except Exception:
            import logging

            logging.exception("Verification job failed")
            job.update(
                error="Verification failed. Check backend logs or try offline mode."
            )
        finally:
            job.update(done=True)

    task = asyncio.create_task(work())
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return JSONResponse({"job_id": key}, 202)


@app.get("/api/jobs/{key}")
def job_status(key: str):
    if key not in jobs:
        raise HTTPException(404, "Job expired or server restarted.")
    return jobs[key]


@app.post("/api/evaluate")
async def evaluate(
    limit: int = Query(3, ge=1, le=10), repeats: int = Query(2, ge=1, le=3)
):
    if not provider()[2]:
        raise HTTPException(
            503, "Configure a free-tier model key to run the prompt comparison."
        )
    return await run_evaluation(limit, repeats)


dist = ROOT / "frontend/dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
