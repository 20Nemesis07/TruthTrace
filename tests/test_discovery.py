import unittest
from unittest.mock import patch

import httpx

from backend.services.web_discovery import discover
from backend.services.pib import releases


class Discovery(unittest.IsolatedAsyncioTestCase):
    async def test_only_fetched_article_becomes_evidence(self):
        def transport(request):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "Unverified model prose https://unrelated.example/fake https://news.un.org/en/story/1"
                            }
                        }
                    ]
                },
            )

        article = dict(
            title="Article",
            date="",
            author="",
            text="Words actually in the publication.",
        )
        with patch(
            "backend.services.web_discovery.extract_article", return_value=article
        ) as read:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(transport)
            ) as client:
                rows = await discover(
                    client,
                    "openai/gpt-oss-20b",
                    "dummy",
                    ["peace talks"],
                    lambda: "today",
                )
        read.assert_awaited_once_with("https://news.un.org/en/story/1")
        self.assertEqual([row["text"] for row in rows], [article["text"]])

    async def test_pib_relative_redirect(self):
        def transport(request):
            if request.url.path == "/RssMain.aspx":
                return httpx.Response(302, headers={"location": "/feed"})
            return httpx.Response(
                200,
                text="<rss><channel><item><title>Release</title>"
                "<link>https://pib.gov.in/Release</link>"
                "<description>A complete press release description for this test.</description>"
                "</item></channel></rss>",
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            rows = await releases(client, lambda: "today")
        self.assertEqual(rows[0]["title"], "Release")
