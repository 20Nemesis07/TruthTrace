from collections import defaultdict
from statistics import mean
from sklearn.metrics import f1_score


def metrics(rows):
    ok = [r for r in rows if "verdict" in r]
    result = {
        "attempts": len(rows),
        "usable_responses": len(ok),
        "errors": len(rows) - len(ok),
    }
    if not ok:
        return result
    gold = [r["expected"] for r in ok]
    pred = [r["verdict"] for r in ok]
    groups = defaultdict(list)
    for r in ok:
        groups[r["case"]].append(r["verdict"])
    pairs = [len(set(v)) == 1 for v in groups.values() if len(v) > 1]
    citations = sum(r["cited"] for r in ok)
    relevant = sum(r["relevant"] for r in ok)
    definitive = [r for r in ok if r["verdict"] != "UNVERIFIABLE"]
    result.update(
        accuracy=mean(a == b for a, b in zip(gold, pred)),
        macro_f1=f1_score(
            gold,
            pred,
            labels=["TRUE", "FALSE", "MISLEADING", "UNVERIFIABLE"],
            average="macro",
            zero_division=0,
        ),
        citation_validity=sum(r["valid"] for r in ok) / citations
        if citations
        else None,
        evidence_relevance=relevant / citations if citations else None,
        unsupported_claim_rate=mean(
            not r["valid"]
            or r["valid"] != r["cited"]
            or not r["relevant"]
            or r["expected"] != r["verdict"]
            for r in definitive
        )
        if definitive
        else None,
        unverifiable_f1=f1_score(
            [v == "UNVERIFIABLE" for v in gold],
            [v == "UNVERIFIABLE" for v in pred],
            zero_division=0,
        ),
        consistency=mean(pairs) if pairs else None,
        mean_latency_seconds=mean(r["seconds"] for r in rows),
    )
    return result
