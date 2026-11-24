import hashlib
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .document_extractor import chunks
from .source_assessor import assess


def rank(docs, analysis):
    passages = []
    seen = set()
    for d in sorted(docs, key=lambda item: {"live":0, "cached":1, "offline":2}.get(item["mode"],3)):
        if d["url"] in seen:
            continue
        seen.add(d["url"])
        for passage in list(chunks(d["text"]))[:14]:
            passages.append((d, passage))
    if not passages:
        return []
    texts = [d["title"] + " " + p for d, p in passages]
    try:
        matrix = TfidfVectorizer(
            ngram_range=(1, 2), strip_accents="unicode", stop_words="english"
        ).fit_transform(analysis.assertions + texts)
    except ValueError:
        return []
    n = len(analysis.assertions)
    scores = cosine_similarity(matrix[:n], matrix[n:])
    ranked = []
    for i, (doc, passage) in enumerate(passages):
        rel = [round(float(x), 3) for x in scores[:, i]]
        if max(rel) < 0.075:
            continue
        credibility, indicators = assess(doc, analysis.topic)
        digest = hashlib.sha256((doc["url"] + "\n" + passage).encode()).hexdigest()[:16]
        ranked.append(
            dict(
                **{k: v for k, v in doc.items() if k != "text"},
                text=passage,
                id=digest,
                relevance=rel,
                credibility=credibility,
                indicators=indicators,
                score=0.8 * max(rel) + 0.2 * credibility,
            )
        )
    ranked.sort(key=lambda d: d["score"], reverse=True)
    result = []

    def tokens(p):
        return set(re.findall(r"\w+", p.lower()))

    for d in ranked:
        a = tokens(d["text"])
        if any(
            len(a & b) / max(1, len(a | b)) > 0.78
            for b in (tokens(e["text"]) for e in result)
        ):
            continue
        if sum(e["url"] == d["url"] for e in result) >= 2:
            continue
        result.append(d)
        if len(result) == 10:
            break
    return result
