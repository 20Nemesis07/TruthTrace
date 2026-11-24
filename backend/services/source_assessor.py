import json
from ..config import ROOT
from urllib.parse import urlparse
from datetime import datetime, timezone

WEIGHTS = json.loads((ROOT / "backend/source_weights.json").read_text(encoding="utf-8"))
AUTHORITY = {
    "nvidianews.nvidia.com": "leadership",
    "investor.nvidia.com": "leadership",
    "www.nvidia.com": "leadership",
    "www.sebi.gov.in": "finance",
    "www.mohfw.gov.in": "health",
    "www.pmindia.gov.in": "public affairs",
    "www.pib.gov.in": "public affairs",
    "pib.gov.in": "public affairs",
    "science.nasa.gov": "space",
    "www.who.int": "health",
    "www.rbi.org.in": "finance",
}


def assess(doc, topic):
    host = urlparse(doc["url"]).hostname
    indicators = {
        "traceable": bool(host and doc["title"]),
        "identified publisher": bool(doc["publisher"]),
        "named author": bool(doc["author"]),
        "publication date": bool(doc["date"]),
        "topic authority": AUTHORITY.get(host) == topic,
        "primary institutional statement": bool(
            doc["primary"] and AUTHORITY.get(host) == topic
        ),
        "indexed research": doc["adapter"] in ("Europe PMC", "Crossref"),
    }
    indicators = [k for k, v in indicators.items() if v]
    return round(min(1, sum(WEIGHTS[k] for k in indicators)), 3), indicators


def current_enough(date):
    try:
        return (
            0
            <= (
                datetime.now(timezone.utc).date()
                - datetime.fromisoformat(date[:10]).date()
            ).days
            <= 90
        )
    except ValueError:
        return False
