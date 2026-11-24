def adjudicate(analysis, findings, docs):
    registry = {d["id"]: d for d in docs}
    results = []
    for index, assertion in enumerate(analysis.assertions):
        relevant = [f for f in findings if f.assertion == index]
        labels = {f.relation for f in relevant}
        citations = [registry[f.evidence_id] for f in relevant]
        primary = any(d["primary"] and d["credibility"] >= 0.7 for d in citations)
        # Count the same first author or DOI once across indexes and publishers.
        representatives = []
        for d in citations:
            if d["credibility"] < 0.4:
                continue
            author = d.get("author", "").partition(",")[0].casefold().strip()
            if any(
                d["publisher"].casefold() == e["publisher"].casefold()
                or (
                    author
                    and author
                    == e.get("author", "").partition(",")[0].casefold().strip()
                )
                or (
                    d.get("title")
                    and d["title"].casefold() == e.get("title", "").casefold()
                )
                for e in representatives
            ):
                continue
            representatives.append(d)
        qualified = {d["publisher"].casefold() for d in representatives}
        enough = primary or len(qualified) >= 2
        decision = "UNVERIFIABLE"
        if analysis.kind == "factual" and enough and len(labels) == 1:
            decision = {
                "Supports": "TRUE",
                "Contradicts": "FALSE",
                "Partially supports": "MISLEADING",
            }[labels.pop()]
        results.append(
            dict(
                assertion=assertion,
                verdict=decision,
                independent_publishers=len(qualified),
                conflicting=len({f.relation for f in relevant}) > 1,
                ids=[f.evidence_id for f in relevant],
            )
        )
    verdicts = {r["verdict"] for r in results}
    if "UNVERIFIABLE" in verdicts:
        final = "UNVERIFIABLE"
    elif len(verdicts) == 1:
        final = next(iter(verdicts))
    else:
        final = "MISLEADING"
    return final, results
