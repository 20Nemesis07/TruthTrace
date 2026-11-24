"""Translate evidence decisions into user-facing outcomes, including older saved reports."""

PENDING = "UNVERIFIABLE"
PROVISIONAL = {
    "Supports": "LIKELY TRUE",
    "Contradicts": "LIKELY FALSE",
    "Partially supports": "POSSIBLY MISLEADING",
}


def outcome_report(report):
    if report.get("outcome_version") == 1:
        return report
    kind = report["analysis"]["kind"]
    nonfactual = {
        "opinion": "OPINION",
        "prediction": "PREDICTION",
        "ambiguous": "NEEDS CLARIFICATION",
    }
    failure = (
        report.get("verification_error")
        or report.get("interpretation_mode") == "model unavailable"
    )
    for index, part in enumerate(report["subclaims"]):
        if part["verdict"] != PENDING:
            continue
        labels = {f["relation"] for f in report["findings"] if f["assertion"] == index}
        if kind in nonfactual:
            status = nonfactual[kind]
        elif len(labels) > 1:
            status = "CONFLICTING EVIDENCE"
        elif labels and not report["validation_failures"]:
            status = PROVISIONAL.get(next(iter(labels)), "NEEDS EVIDENCE")
        else:
            status = "CHECK INCOMPLETE" if failure else "NEEDS EVIDENCE"
        part["verdict"] = status

    if report["verdict"] == PENDING:
        statuses = {p["verdict"] for p in report["subclaims"]}
        if failure:
            status = "CHECK INCOMPLETE"
        elif kind in nonfactual:
            status = nonfactual[kind]
        elif report["validation_failures"]:
            status = "CHECK INCOMPLETE"
        elif len(statuses) == 1 and next(iter(statuses)) not in {
            "TRUE",
            "FALSE",
            "MISLEADING",
        }:
            status = next(iter(statuses))
        elif statuses <= {"TRUE", "LIKELY TRUE"} and "LIKELY TRUE" in statuses:
            status = "LIKELY TRUE"
        elif statuses <= {"FALSE", "LIKELY FALSE"} and "LIKELY FALSE" in statuses:
            status = "LIKELY FALSE"
        elif len(statuses) > 1:
            status = "PARTIAL ASSESSMENT"
        else:
            status = "NEEDS REVIEW"
        report["verdict"] = status
        report["summary"]["interpretation"] = " ".join(
            f"{p['assertion']} — {p['verdict']}." for p in report["subclaims"]
        )
        if "verdict" in report["summary"]:
            report["summary"]["verdict"] = status
        if status in PROVISIONAL.values():
            report["summary"]["uncertainty"] = (
                "The cited passages agree. Independent corroboration is limited."
            )
    report["outcome_version"] = 1
    return report
