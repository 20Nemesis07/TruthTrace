import re
from .source_assessor import current_enough


def validate(findings, passages, assertions):
    registry = {d["id"]: d for d in passages}
    accepted = []
    errors = []
    seen = {}
    for f in findings:
        doc = registry.get(f.evidence_id)
        key = (f.assertion, f.evidence_id)
        reason = None
        if f.assertion >= len(assertions):
            reason = "unknown assertion"
        elif doc is None:
            reason = "unknown evidence ID"
        elif f.relation in ("Irrelevant", "Insufficient evidence"):
            continue
        elif (
            len(f.quote.strip()) < 8
            or not f.quote.strip()
            or f.quote not in doc["text"]
        ):
            reason = "quotation absent or too short"
        elif doc["relevance"][f.assertion] < 0.075:
            reason = "low textual relevance"
        elif re.search(
            r"\b(currently|today|right now|latest)\b", assertions[f.assertion], re.I
        ) and not current_enough(
            doc["retrieved"] if doc.get("maintained_profile") else doc["date"]
        ):
            reason = "undated or stale for current claim"
        elif key in seen:
            reason = "duplicate or inconsistent annotation"
        if reason:
            errors.append(
                {"id": f.evidence_id, "assertion": f.assertion, "reason": reason}
            )
        else:
            seen[key] = f.relation
            accepted.append(f)
    return accepted, errors
