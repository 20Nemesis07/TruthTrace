import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import database, config
from backend.services.evidence_retriever import search_one
from backend.services.publisher_page import fetch
from backend.services.evidence_validator import validate
from backend.schemas import Finding


class Retrieval(unittest.IsolatedAsyncioTestCase):
    async def test_wiki_cache_preserves_timestamp(self):
        calls = []

        def transport(req):
            calls.append(req)
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": {
                            "1": {
                                "title": "Test document",
                                "fullurl": "https://en.wikipedia.org/wiki/Example",
                                "extract": "A fictional test document for the integration test.",
                            }
                        }
                    }
                },
            )

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(config, "DB", Path(tmp) / "db"),
        ):
            database.init()
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(transport)
            ) as client:
                first = await search_one(client, "Wikipedia", "example")
                second = await search_one(client, "Wikipedia", "example")
        self.assertEqual(len(calls), 1)
        self.assertEqual(first[0]["mode"], "live")
        self.assertEqual(second[0]["mode"], "cached")
        self.assertEqual(first[0]["retrieved"], second[0]["retrieved"])

    async def test_all_grounded_queries_reach_search(self):
        from unittest.mock import AsyncMock
        from backend.schemas import Analysis
        from backend.services.claim_processor import analyze
        from backend.services.evidence_retriever import retrieve

        plan = Analysis(kind="factual", topic="general", assertions=["Treaty in 2005"],
                        entities=[], qualifiers=[], queries=[
                            "treaty 2005", "disarmament 2013", "accord terms", "signatories"
                        ])
        search = AsyncMock(return_value=[])
        with (
            patch("backend.services.claim_processor.interpret", return_value=plan),
            patch("backend.services.evidence_retriever.search_one", search),
        ):
            analysis, _ = await analyze("A treaty was signed in 2005.")
            await retrieve(analysis)
        sent = [call.args[2] for call in search.await_args_list if call.args[1] == "Wikipedia"]
        self.assertEqual(sent, ["treaty 2005", "disarmament", "accord terms", "signatories"])

    async def test_stale_policy(self):
        f = Finding(
            assertion=0,
            evidence_id="x",
            quote="was still legal tender",
            relation="Supports",
            reason="Historical notice",
        )
        v, e = validate(
            [f],
            [
                dict(
                    id="x",
                    text="It was still legal tender",
                    relevance=[0.6],
                    date="2023-05-19",
                )
            ],
            ["It is currently legal tender."],
        )
        self.assertFalse(v)
        self.assertIn("stale", e[0]["reason"])

    async def test_private_dns(self):
        from unittest.mock import AsyncMock
        import asyncio

        with patch.object(
            asyncio.get_running_loop(),
            "getaddrinfo",
            AsyncMock(return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]),
        ):
            with self.assertRaisesRegex(ValueError, "Non-public"):
                await fetch("https://www.who.int/test", 50)
