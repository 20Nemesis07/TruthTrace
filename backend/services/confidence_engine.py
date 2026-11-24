def confidence(verdict, subclaims, findings, docs, errors):
    covered = sum(s["verdict"] != "UNVERIFIABLE" for s in subclaims)
    ids = {f.evidence_id for f in findings}
    used = [d for d in docs if d["id"] in ids]
    groups = min((s["independent_publishers"] for s in subclaims), default=0)
    strong = bool(used) and all(
        d["credibility"] >= 0.55 and max(d["relevance"]) >= 0.18 for d in used
    )
    high = groups >= 2 and strong and not errors
    level = "Low" if verdict == "UNVERIFIABLE" else "High" if high else "Medium"
    reason = f"{covered}/{len(subclaims)} assertions met the evidence rules. {len(ids)} cited passages passed quotation checks. Minimum publisher count per assertion: {groups}."
    return {"level": level, "reason": reason, "validation_failures": len(errors)}
