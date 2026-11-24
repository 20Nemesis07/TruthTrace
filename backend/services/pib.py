from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from urllib.parse import urljoin, urlsplit
from .document_extractor import plain


async def releases(client, stamp):
    url = "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1"
    for _ in range(4):
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get("location", ""))
                target = urlsplit(url)
                if target.scheme != "https" or target.netloc not in (
                    "www.pib.gov.in",
                    "pib.gov.in",
                ):
                    raise ValueError("Unrecognized PIB redirect")
                continue
            response.raise_for_status()
            data = bytearray()
            async for block in response.aiter_bytes():
                data.extend(block)
                if len(data) > 1_500_000:
                    raise ValueError("RSS response too large")
            break
    else:
        raise ValueError("Too many PIB redirects")
    if b"<!ENTITY" in bytes(data).upper():
        raise ValueError("Unsupported RSS declarations")
    result = []
    for item in ET.fromstring(data).findall(".//item")[:45]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        body = plain(item.findtext("description", ""))
        if (
            urlsplit(link).hostname not in ("www.pib.gov.in", "pib.gov.in")
            or urlsplit(link).scheme != "https"
        ):
            continue
        if len(body) < 30 or body == title:
            continue
        try:
            date = (
                parsedate_to_datetime(item.findtext("pubDate", "")).date().isoformat()
            )
        except (ValueError, TypeError):
            date = ""
        result.append(
            dict(
                title=title,
                url=link,
                text=body[:5000],
                publisher="Press Information Bureau",
                author="",
                date=date,
                retrieved=stamp(),
                adapter="PIB press releases",
                mode="live",
                primary=True,
            )
        )
    return result
