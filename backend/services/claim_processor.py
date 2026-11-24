import re
from ..schemas import Analysis
from .gemini_service import interpret, prompt, ModelUnavailable


async def analyze(claim, use_ai=True):
    normalized = " ".join(claim.split())
    if use_ai:
        try:
            analysis = await interpret(prompt("P1"), {"claim": normalized}, Analysis)
            year_pattern = r"\b(?:1[0-9]{3}|20[0-9]{2})\b"
            stated_years = set(re.findall(year_pattern, normalized))
            queries = []
            for query in analysis.queries:
                grounded = re.sub(
                    year_pattern,
                    lambda match: match[0] if match[0] in stated_years else "",
                    query,
                )
                grounded = " ".join(grounded.split())
                if grounded and grounded not in queries:
                    queries.append(grounded)
            analysis.queries = queries or [normalized[:240]]
            return analysis, []
        except ModelUnavailable as exc:
            warning = str(exc)
    else:
        warning = "Local claim analysis selected."
    topics = {
        "leadership": r"\b(ceo|chief executive|reappointed|succeeded as)\b",
        "health": r"covid|virus|vaccine|health|disease",
        "space": r"planet|mars|venus|mercury|solar|moon",
        "finance": r"bank|rbi|rupee|currency",
        "public affairs": r"government|election|minister",
    }
    topic = next(
        (t for t, p in topics.items() if re.search(p, normalized, re.I)), "general"
    )
    parts = re.split(r";\s*|\s+and\s+(?=(?:[A-Z][a-z]+|the |it |they ))", normalized)
    parts = [part.strip() for part in parts if part.strip()] or [normalized]
    if len(parts) > 6:
        parts = [normalized]
    kind = (
        "opinion"
        if re.search(r"\b(best|prettiest|most beautiful)\b", normalized, re.I)
        else "prediction"
        if re.search(
            r"\bwill (definitely |certainly )?(win|discover|become)\b", normalized, re.I
        )
        else "factual"
    )
    words = re.findall(r"\b[A-Z][\w-]*\b", normalized)
    qualifiers = re.findall(
        r"\b(?:\d+[\w%.-]*|today|currently|every|only|always|never)\b", normalized, re.I
    )
    return Analysis(
        kind=kind,
        topic=topic,
        assertions=parts,
        entities=words[:20],
        qualifiers=qualifiers[:20],
        queries=[normalized[:220], normalized[:180] + " fact check evidence against"],
    ), [warning]
