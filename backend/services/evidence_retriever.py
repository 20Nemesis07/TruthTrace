"""Search public indexes and fetch evidence from approved publishers."""

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse, quote
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from ..config import ROOT, provider
from .web_discovery import BROWSER_MODELS, discover
from .. import database
from .document_extractor import plain
from .publisher_page import extract, HOSTS
from .pib import releases

AGENT = "TruthTraceUniversity/1.0"
URLS = {
    "Fact Check Tools": "https://factchecktools.googleapis.com/v1alpha1/claims:search",
    "Wikipedia": "https://en.wikipedia.org/w/api.php",
    "Europe PMC": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    "Crossref": "https://api.crossref.org/works",
    "FactCheck.org": "https://www.factcheck.org/wp-json/wp/v2/posts",
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def local_docs():
    return json.loads(
        (ROOT / "datasets/source_documents/catalog.json").read_text(encoding="utf-8")
    )


async def get_json(client, url, params):
    async with client.stream("GET", url, params=params) as r:
        r.raise_for_status()
        if r.is_redirect:
            raise ValueError("redirect refused")
        data = bytearray()
        async for chunk in r.aiter_bytes():
            data.extend(chunk)
            if len(data) > 2_000_000:
                raise ValueError("response too large")
    return json.loads(data)


async def search_one(client, source, query):
    cachekey = hashlib.sha256((source + query).encode()).hexdigest()
    cached = database.cache_get(cachekey)
    if cached is not None:
        return [dict(item, mode="cached") for item in cached]
    if source == "GOV.UK":
        hits = await get_json(
            client,
            "https://www.gov.uk/api/search.json",
            {
                "q": query,
                "count": 3,
                "filter_format": ["news_article", "speech", "press_release"],
            },
        )

        async def publication(hit):
            path = hit.get("link", "")
            if not path.startswith("/government/") or "?" in path or "#" in path:
                return None
            data = await get_json(client, "https://www.gov.uk/api/content" + path, {})
            body = data.get("details", {}).get("body")
            if not isinstance(body, str) or len(text := plain(body)) < 60:
                return None
            orgs = data.get("links", {}).get("organisations", [])
            return dict(
                title=data["title"],
                url="https://www.gov.uk" + path,
                text=text[:15000],
                author=", ".join(o["title"] for o in orgs),
                publisher="UK Government",
                date=(data.get("first_published_at") or "")[:10],
                adapter=source,
                primary=False,
                mode="live",
                retrieved=stamp(),
            )

        pages = await asyncio.gather(
            *(publication(hit) for hit in hits.get("results", [])),
            return_exceptions=True,
        )
        rows = [page for page in pages if isinstance(page, dict)]
        if not rows and any(isinstance(page, Exception) for page in pages):
            raise ValueError(
                "retrieved search results but could not read the publications"
            )
        if rows:
            database.cache_put(cachekey, rows)
        return rows
    if source == "Groq web search":
        _, model, key = provider()
        rows = await discover(client, model, key, query.splitlines(), stamp)
        database.cache_put(cachekey, rows)
        return rows
    if source == "Prime Minister’s Office":
        url = "https://www.pmindia.gov.in/en/pms-profile/"
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 1_500_000:
                    raise ValueError("Profile page too large")
        soup = BeautifulSoup(bytes(data), "html.parser")
        article = (
            soup.select_one(".alignimage") or soup.find("article") or soup.find("main")
        )
        text = (
            "\n".join(p.get_text(" ", strip=True) for p in article.select("p"))
            if article
            else ""
        )
        if len(text) < 60:
            raise ValueError("Profile has no readable biography")
        rows = [
            dict(
                title="Prime Minister of India – official profile",
                url=url,
                text=text[:15000],
                publisher=source,
                author=source,
                date="",
                retrieved=stamp(),
                adapter=source,
                mode="live",
                primary=True,
                maintained_profile=True,
            )
        ]
        database.cache_put(cachekey, rows)
        return rows
    if source == "Official leadership announcement":
        record = next(
            d for d in local_docs() if d["adapter"] == source and d["url"] == query
        )
        body = await extract(record["url"])
        if not body.strip():
            raise ValueError("No readable announcement")
        rows = [dict(record, text=body, retrieved=stamp(), mode="live")]
        database.cache_put(cachekey, rows)
        return rows
    if source == "PIB":
        rows = await releases(client, stamp)
        database.cache_put(cachekey, rows)
        return rows
    url = URLS[source]
    rows = []

    def add(title, link, body, publisher, author="", date="", primary=False):
        parsed = urlparse(link)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return
        text = plain(body)
        if title and len(text) > 20:
            rows.append(
                dict(
                    title=plain(title),
                    url=link,
                    text=text[:15000],
                    publisher=publisher or source,
                    author=author or "",
                    date=date or "",
                    retrieved=stamp(),
                    adapter=source,
                    mode="live",
                    primary=primary,
                )
            )

    if source == "Wikipedia":
        data = await get_json(
            client,
            url,
            dict(
                action="query",
                format="json",
                generator="search",
                gsrsearch=query,
                gsrlimit=3,
                prop="extracts|info",
                inprop="url",
                exintro=1,
                explaintext=1,
                exsentences=7,
            ),
        )
        for item in data.get("query", {}).get("pages", {}).values():
            add(item["title"], item["fullurl"], item.get("extract", ""), "Wikipedia")
    elif source == "Europe PMC":
        data = await get_json(
            client, url, dict(query=query, format="json", resultType="core", pageSize=4)
        )
        for i in data.get("resultList", {}).get("result", []):
            if not i.get("id") or not i.get("source"):
                continue
            link = (
                "https://europepmc.org/article/"
                + quote(i["source"], safe="")
                + "/"
                + quote(i["id"], safe="")
            )
            add(
                i.get("title"),
                link,
                i.get("abstractText"),
                i.get("journalInfo", {}).get("journal", {}).get("title"),
                i.get("authorString"),
                i.get("firstPublicationDate"),
            )
    elif source == "Crossref":
        data = await get_json(
            client,
            url,
            {"query.bibliographic": query, "filter": "has-abstract:true", "rows": 4},
        )
        for i in data["message"]["items"]:
            author = ", ".join(a.get("family", "") for a in i.get("author", [])[:3])
            date = "-".join(map(str, i.get("published", {}).get("date-parts", [[]])[0]))
            add(
                (i.get("title") or [""])[0],
                i.get("URL", ""),
                i.get("abstract"),
                i.get("publisher"),
                author,
                date,
            )
    elif source == "Fact Check Tools":
        # The search index provides links; verdict evidence must come from the publisher page.
        async with httpx.AsyncClient(
            timeout=6, headers={"x-goog-api-key": os.environ["FACTCHECK_API_KEY"]}
        ) as fact_client:
            data = await get_json(
                fact_client, url, dict(query=query, pageSize=4, languageCode="en")
            )
        for claim in data.get("claims", []):
            for review in claim.get("claimReview", [])[:1]:
                link = review.get("url", "")
                if urlparse(link).hostname not in HOSTS:
                    continue
                try:
                    body = await extract(link)
                except (ValueError, httpx.HTTPError, OSError):
                    continue
                add(
                    review.get("title"),
                    link,
                    body,
                    review.get("publisher", {}).get("name"),
                    date=review.get("reviewDate", "")[:10],
                )
    else:
        # Respect this publisher's robots policy before using its public WordPress read API.
        rules = await client.get("https://www.factcheck.org/robots.txt")
        if rules.status_code != 404:
            rules.raise_for_status()
            rp = RobotFileParser()
            rp.parse(rules.text.splitlines())
            if not rp.can_fetch(AGENT, url):
                raise ValueError("publisher disallows access")
        data = await get_json(
            client,
            url,
            dict(search=query, per_page=3, _fields="title,link,content,date"),
        )
        for i in data:
            add(
                i["title"]["rendered"],
                i["link"],
                i["content"]["rendered"],
                "FactCheck.org",
                date=i["date"][:10],
            )
    database.cache_put(cachekey, rows)
    return rows


async def retrieve(analysis, offline=False):
    docs = local_docs()
    if offline:
        return docs, ["Offline mode uses the bundled source collection."]
    sources = [
        "Wikipedia",
        "FactCheck.org",
        "Europe PMC" if analysis.topic == "health" else "Crossref",
    ]
    if analysis.topic in {"public affairs", "general", "leadership", "finance"}:
        sources.append("GOV.UK")
    if os.getenv("FACTCHECK_API_KEY"):
        sources.append("Fact Check Tools")
    tasks = [(s, q[:240]) for s in sources for q in analysis.queries]
    if analysis.topic in ("finance", "public affairs"):
        tasks.append(("PIB", "latest releases"))
    query_text = " ".join(
        analysis.assertions + analysis.entities + analysis.queries
    ).casefold()
    if "india" in query_text and "prime minister" in query_text:
        tasks.append(("Prime Minister’s Office", "current officeholder profile"))
    name, model, key = provider()
    if (
        os.getenv("GROQ_BROWSER_SEARCH") == "1"
        and name == "groq"
        and key
        and model in BROWSER_MODELS
    ):
        tasks.append(("Groq web search", "\n".join(analysis.queries)))
    for doc in docs:
        if (
            doc["adapter"] == "Official leadership announcement"
            and doc["subject"].casefold() in query_text
        ):
            tasks.append((doc["adapter"], doc["url"]))
    warnings = []
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(7), follow_redirects=False, headers={"User-Agent": AGENT}
    ) as client:
        results = await asyncio.gather(
            *(
                asyncio.wait_for(
                    search_one(client, s, q), 65 if s == "Groq web search" else 20
                )
                for s, q in tasks
            ),
            return_exceptions=True,
        )
    for (source, _), items in zip(tasks, results):
        if isinstance(items, BaseException):
            warnings.append(
                source
                + " search unavailable ("
                + (
                    "HTTP " + str(items.response.status_code)
                    if isinstance(items, httpx.HTTPStatusError)
                    else str(items)
                    if isinstance(items, ValueError)
                    else type(items).__name__
                )
                + ")."
            )
        else:
            docs.extend(items)
    return docs, list(dict.fromkeys(warnings))
