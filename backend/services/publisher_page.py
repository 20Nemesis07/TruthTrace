"""Fetch approved publisher HTML only. Pin a public IP and verify TLS for the original host."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup

HOSTS = {
    "news.un.org",
    "press.un.org",
    "colombia.unmissions.org",
    "www.un.org",
    "www.gov.uk",
    "www.pmindia.gov.in",
    "www.bbc.com",
    "www.theguardian.com",
    "apnews.com",
    "www.reuters.com",
    "www.nasa.gov",
    "nvidianews.nvidia.com",
    "investor.nvidia.com",
    "www.nvidia.com",
    "www.boomlive.in",
    "www.altnews.in",
    "pib.gov.in",
    "www.pib.gov.in",
    "www.who.int",
    "www.rbi.org.in",
    "www.sebi.gov.in",
    "www.mohfw.gov.in",
    "www.factcheck.org",
    "fullfact.org",
    "factcheck.afp.com",
    "science.nasa.gov",
}
AGENT = "TruthTraceUniversity/1.0"


async def fetch(url, limit):
    target = urlsplit(url)
    if (
        target.scheme != "https"
        or target.hostname not in HOSTS
        or target.port not in (443, None)
        or target.username
        or target.password
    ):
        raise ValueError("Publisher URL outside allowlist")
    records = await asyncio.get_running_loop().getaddrinfo(
        target.hostname, 443, type=socket.SOCK_STREAM
    )
    ips = [ipaddress.ip_address(r[4][0]) for r in records]
    if not ips or any(not ip.is_global or ip.is_multicast for ip in ips):
        raise ValueError("Non-public destination")
    ip = next((i for i in ips if i.version == 4), ips[0])
    address = httpx.URL(url).copy_with(host=str(ip))
    async with httpx.AsyncClient(
        timeout=5, trust_env=False, follow_redirects=False
    ) as client:
        async with client.stream(
            "GET",
            address,
            headers={"Host": target.hostname, "User-Agent": AGENT},
            extensions={"sni_hostname": target.hostname},
        ) as res:
            if res.status_code == 404 and target.path == "/robots.txt":
                return ""
            res.raise_for_status()
            if target.path != "/robots.txt" and "text/html" not in res.headers.get(
                "content-type", ""
            ):
                raise ValueError("Expected HTML")
            data = bytearray()
            async for piece in res.aiter_bytes():
                data.extend(piece)
                if len(data) > limit:
                    raise ValueError("Publisher response too large")
            return data.decode(res.encoding or "utf-8", errors="replace")


async def extract_article(url):
    host = urlsplit(url).hostname
    if host not in HOSTS:
        raise ValueError("Unknown publisher")
    rp = RobotFileParser()
    rp.parse((await fetch("https://" + host + "/robots.txt", 200000)).splitlines())
    if not rp.can_fetch(AGENT, url):
        raise ValueError("Disallowed by publisher")
    soup = BeautifulSoup(await fetch(url, 1_500_000), "html.parser")
    article = soup.find("article") or soup.find("main") or soup.select_one("#content")
    if article is None:
        raise ValueError("No readable article")
    for tag in article.select("script,style,nav,aside,footer,form"):
        tag.decompose()

    def meta(selector):
        tag = soup.select_one(selector)
        return tag.get("content", "") if tag else ""

    heading = soup.find("h1") or soup.title
    return dict(
        title=heading.get_text(" ", strip=True) if heading else host,
        text="\n".join(p.get_text(" ", strip=True) for p in article.find_all("p"))[
            :15000
        ],
        author=meta('meta[name="author"]'),
        date=meta('meta[property="article:published_time"]')[:10],
    )


async def extract(url):
    return (await extract_article(url))["text"]
