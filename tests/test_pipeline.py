import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from backend import config
from backend.main import app, requests_by_ip
from backend.schemas import Finding, Findings, Synthesis
from backend.services.evidence_retriever import local_docs
from backend.services.publisher_page import fetch
from backend.services.pipeline import verify
from backend.schemas import Claim
from backend.services.document_extractor import plain
from backend.services.verdict_engine import adjudicate
from backend.services.claim_processor import analyze


class Desk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(config, "DB", Path(self.tmp.name) / "db")
        self.db.start()
        self.api = TestClient(app)
        self.api.__enter__()
        requests_by_ip.clear()

    def tearDown(self):
        self.api.__exit__(None, None, None)
        self.db.stop()
        self.tmp.cleanup()

    def check(self, claim):
        r = self.api.post("/api/verify", json={"claim": claim, "offline": True})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_end_to_end_and_history(self):
        r = self.check("Mars has no rings.")
        self.assertEqual(r["verdict"], "TRUE")
        self.assertTrue(r["findings"])
        self.assertEqual(
            self.api.get("/api/history", params={"q": "Mars"}).json()[0]["id"], r["id"]
        )
        self.assertEqual(self.api.get("/api/history/" + r["id"]).json(), r)
        f = r["findings"][0]
        for bad in [
            dict(f, quote="This is invented."),
            dict(f, evidence_id="fake"),
            dict(f, assertion=5),
        ]:
            v = self.api.post(
                "/api/evidence/validate", json={"report_id": r["id"], "findings": [bad]}
            ).json()
            self.assertFalse(v["valid"])
            self.assertTrue(v["failures"])

    def test_absent_opinion_and_partial_coverage(self):
        for claim, expected in [
            ("The cafeteria will close at noon.", "NEEDS EVIDENCE"),
            ("Venus is the prettiest planet.", "OPINION"),
            ("Mars has no rings and Jupiter makes coffee.", "PARTIAL ASSESSMENT"),
        ]:
            self.assertEqual(self.check(claim)["verdict"], expected)

    def test_input_and_unknown_history(self):
        self.assertEqual(
            self.api.post("/api/verify", json={"claim": "   "}).status_code, 422
        )
        self.assertEqual(self.api.get("/api/history/absent").status_code, 404)

    def test_html(self):
        self.assertEqual(
            plain("<nav>Home</nav><p>Real words.</p><script>bad()</script>"),
            "Real words.",
        )

    def test_all_examples_output_without_provider(self):
        from backend.config import ROOT
        import json

        for c in json.loads(
            (ROOT / "datasets/benchmark_claims.json").read_text(encoding="utf-8")
        ):
            self.assertIn(
                c["reference_passage"], local_docs()[c["document_indexes"][0]]["text"]
            )

    def test_optional_eval_needs_key(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "GEMINI_API_KEY": ""}):
            self.assertEqual(self.api.post("/api/evaluate").status_code, 503)


class Guards(unittest.IsolatedAsyncioTestCase):
    async def test_block_destinations(self):
        for link in [
            "http://localhost",
            "https://127.0.0.1",
            "https://www.who.int@evil.example/x",
            "https://www.who.int:8443/x",
        ]:
            with self.assertRaises(ValueError):
                await fetch(link, 100)

    async def test_conflict_and_independence(self):
        a, _ = await analyze("Mars has rings.", False)
        docs = [
            dict(id=str(i), publisher="NASA", primary=False, credibility=0.6)
            for i in range(2)
        ]
        f = [
            Finding(
                assertion=0,
                evidence_id=str(i),
                relation="Supports",
                quote="a direct quote",
                reason="direct",
            )
            for i in range(2)
        ]
        self.assertEqual(adjudicate(a, f, docs)[0], "UNVERIFIABLE")
        docs[0]["primary"] = True
        docs[0]["credibility"] = 0.9
        f[1].relation = "Contradicts"
        self.assertEqual(adjudicate(a, f, docs)[0], "UNVERIFIABLE")


class ModelGates(unittest.IsolatedAsyncioTestCase):
    async def test_synthesis_cannot_override_or_fabricate(self):
        from backend.services.evidence_ranker import rank

        analysis, _ = await analyze("Mars has no rings.", False)
        documents = local_docs()
        item = next(d for d in rank(documents, analysis) if d["title"] == "Mars Facts")
        findings = Findings(
            findings=[
                Finding(
                    assertion=0,
                    evidence_id=item["id"],
                    relation="Supports",
                    quote="Mars has no rings.",
                    reason="Direct statement.",
                )
            ]
        )
        synthesis = Synthesis(
            verdict="FALSE",
            established="Bad result",
            interpretation="",
            uncertainty="",
            citations=["invented"],
        )
        with (
            patch(
                "backend.services.pipeline.provider",
                return_value=("groq", "test", "test"),
            ),
            patch(
                "backend.services.pipeline.analyze",
                AsyncMock(return_value=(analysis, [])),
            ),
            patch(
                "backend.services.pipeline.retrieve",
                AsyncMock(return_value=(documents, [])),
            ),
            patch(
                "backend.services.pipeline.interpret",
                AsyncMock(side_effect=[findings, synthesis]),
            ),
            patch("backend.services.pipeline.database.save"),
        ):
            result = await verify(Claim(claim=analysis.assertions[0]))
        self.assertEqual(result["verdict"], "TRUE")
        self.assertTrue(result["validation_failures"])
        self.assertNotIn("invented", result["summary"]["citations"])
