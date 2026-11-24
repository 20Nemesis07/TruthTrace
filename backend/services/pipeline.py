import re
import uuid
from .. import database
from ..config import provider
from ..schemas import Finding, Findings, Synthesis
from .claim_processor import analyze
from .evidence_retriever import retrieve, stamp
from .evidence_ranker import rank
from .evidence_validator import validate
from .verdict_engine import adjudicate
from .confidence_engine import confidence
from .report_outcome import outcome_report
from .gemini_service import interpret, prompt, ModelUnavailable

STAGES = [
    "Analyzing claim",
    "Retrieving evidence",
    "Assessing sources",
    "Comparing information",
    "Validating citations",
    "Generating verdict",
]


def literal_findings(assertions, docs):
    """Conservative no-key mode: whole sentence equality; no keyword-based decisions."""
    findings = []
    for i, a in enumerate(assertions):
        for d in docs:
            for sentence in re.split(r"(?<=[.!?])\s+", d["text"]):
                if (
                    a.strip().rstrip(".").casefold()
                    == sentence.strip().rstrip(".").casefold()
                ):
                    findings.append(
                        Finding(
                            assertion=i,
                            evidence_id=d["id"],
                            quote=sentence,
                            relation="Supports",
                            reason="Complete sentence matches the assertion.",
                        )
                    )
    return findings


async def verify(request, on_stage=lambda s: None):
    timeline = []

    def stage(name):
        timeline.append({"stage": name, "at": stamp()})
        on_stage(name)

    stage(STAGES[0])
    name, model, key = provider()
    live_ai = bool(key) and not request.offline
    analysis, warnings = await analyze(request.claim, live_ai)
    stage(STAGES[1])
    documents, notes = await retrieve(analysis, request.offline)
    warnings += notes
    stage(STAGES[2])
    docs = rank(documents, analysis)
    stage(STAGES[3])
    mode = "literal comparison"
    failure = None
    findings = []
    if analysis.kind == "factual" and docs:
        if live_ai:
            try:
                response = await interpret(
                    prompt("P2"),
                    {
                        "original_claim": request.claim,
                        "assertions": analysis.assertions,
                        "passages": [
                            {
                                k: d[k]
                                for k in (
                                    "id",
                                    "title",
                                    "text",
                                    "date",
                                    "publisher",
                                    "retrieved",
                                    "maintained_profile",
                                )
                                if k in d
                            }
                            for d in docs
                        ],
                    },
                    Findings,
                )
                findings = response.findings
                mode = name + " / " + model
            except ModelUnavailable as e:
                warnings.append(str(e))
                mode = "model unavailable"
                failure = {"stage": "Comparing evidence", "detail": str(e)}
        else:
            findings = literal_findings(analysis.assertions, docs)
            warnings.append(
                "Literal mode confirms only complete matching statements from sufficient sources. Paraphrases need model comparison."
            )
    if failure:
        findings = literal_findings(analysis.assertions, docs)
        if findings:
            mode = "literal comparison after model error"
    stage(STAGES[4])
    valid, errors = validate(findings, docs, analysis.assertions)
    verdict, parts = adjudicate(analysis, valid, docs)
    if failure and verdict != "UNVERIFIABLE":
        failure = None
    numeric_terms = set(re.findall(r"\d+(?:[.,]\d+)*", request.claim))
    analyzed_terms = set(re.findall(r"\d+(?:[.,]\d+)*", " ".join(analysis.assertions)))
    if numeric_terms - analyzed_terms:
        errors.append(
            {
                "reason": "claim decomposition omitted or reformatted numerical qualifiers"
            }
        )
        verdict = "UNVERIFIABLE"
    if any(e["reason"] == "duplicate or inconsistent annotation" for e in errors):
        verdict = "UNVERIFIABLE"
    stage(STAGES[5])
    synthesis = None
    if (
        live_ai
        and valid
        and verdict != "UNVERIFIABLE"
        and mode != "literal comparison after model error"
    ):
        try:
            summary = await interpret(
                prompt("P3"),
                {
                    "claim": request.claim,
                    "ceiling": verdict,
                    "subclaims": parts,
                    "findings": [f.model_dump() for f in valid],
                },
                Synthesis,
            )
            allowed = {f.evidence_id for f in valid}
            if (
                summary.verdict not in {verdict, "UNVERIFIABLE"}
                or not summary.citations
                or not set(summary.citations) <= allowed
            ):
                errors.append(
                    {"reason": "synthesis verdict or citations failed validation"}
                )
                warnings.append(
                    "Used the validated evidence decision because the written summary failed its checks."
                )
            elif summary.verdict == verdict:
                synthesis = summary.model_dump()
        except ModelUnavailable as e:
            warnings.append(str(e))
            warnings.append(
                "Used the validated evidence decision because the written summary was unavailable."
            )
    if live_ai and docs and mode == name + " / " + model and not valid:
        sources = ", ".join(sorted({d["adapter"] for d in docs}))
        if not findings:
            detail = "The model returned no findings."
        elif errors:
            detail = "No supporting or contradictory quotation passed validation. See the validation details."
        else:
            detail = "The model classified the passages it annotated as irrelevant or insufficient."
        uncertainty = f"Compared {len(docs)} passages from {sources}. {detail}"
    else:
        uncertainty = (
            "Evidence is incomplete, conflicting or insufficiently independent."
        )
    if synthesis is None:
        synthesis = dict(
            established=" ".join(dict.fromkeys(f.quote for f in valid))
            or "No decisive quotation validated.",
            interpretation="; ".join(
                s["assertion"] + " — " + s["verdict"] for s in parts
            ),
            uncertainty=uncertainty
            if verdict == "UNVERIFIABLE"
            else "The assessment is limited to the retrieved passages.",
            citations=list(dict.fromkeys(f.evidence_id for f in valid)),
        )
    result = dict(
        id=uuid.uuid4().hex,
        date=stamp(),
        claim=request.claim,
        timeline=timeline,
        verdict=verdict,
        confidence=confidence(verdict, parts, valid, docs, errors),
        analysis=analysis.model_dump(),
        summary=synthesis,
        subclaims=parts,
        findings=[f.model_dump() for f in valid],
        evidence=docs,
        evidence_modes=sorted({d["mode"] for d in docs}),
        interpretation_mode=mode,
        verification_error=failure,
        limitations=warnings,
        validation_failures=errors,
    )
    outcome_report(result)
    database.save(result)
    return result
