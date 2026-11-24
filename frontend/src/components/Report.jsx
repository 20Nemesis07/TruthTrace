import React from "react";
import { Download, ExternalLink } from "lucide-react";
import { download } from "../services/api";
export default function Report({ r }) {
  const findings = (id) => r.findings.filter((f) => f.evidence_id === id);
  const failure = r.verification_error || (r.interpretation_mode === "model unavailable" && {stage:"Comparing evidence", detail:r.limitations.filter(x=>/groq|gemini|model/i.test(x)).at(-1) || "The model comparison failed."});
  return (
    <article className="card result">
      <div className="row">
        <span className={"badge " + r.verdict.replaceAll(" ", "-")}>{failure ? "CHECK INCOMPLETE" : r.verdict}</span>
        <button onClick={() => download(r)}>
          <Download size={16} /> Download
        </button>
      </div>
      <h2>{r.claim}</h2>
      <small>
        {new Date(r.date).toLocaleString()} · {r.interpretation_mode} · Sources:{" "}
        {r.evidence_modes.join(", ") || "none"}
      </small>
      {failure ? <section role="alert"><h3>{failure.stage} failed</h3><p>{failure.detail}</p><p>The retrieved passages are available below. No final assessment was completed.</p></section> : <>
      <h3>Assessment</h3>
      <p>{r.summary.established}</p>
      <p>{r.summary.interpretation}</p>
      <p>{r.summary.uncertainty}</p>
      <h3>{r.confidence.level} confidence</h3>
      <p>{r.confidence.reason}</p>
      <h3>Assertions</h3>
      {r.subclaims.map((s, i) => (
        <p key={i}>
          <b>{s.verdict}</b> · {s.assertion}
        </p>
      ))}
      </>}
      {["Supports", "Contradicts", "Partially supports"].map((relation) => {
        const matches = r.findings.filter((f) => f.relation === relation);
        return (
          matches.length > 0 && (
            <section key={relation}>
              <h3>
                {
                  {
                    Supports: "Supporting evidence",
                    Contradicts: "Contradictory evidence",
                    "Partially supports": "Context and qualifications",
                  }[relation]
                }
              </h3>
              {matches.map((f, i) => (
                <div key={i}>
                  <blockquote>{f.quote}</blockquote>
                  <a href={"#source-" + f.evidence_id}>
                    {r.evidence.find((d) => d.id === f.evidence_id)?.publisher}{" "}
                    · Inspect passage
                  </a>
                </div>
              ))}
            </section>
          )
        );
      })}
      <h3>Evidence inspection</h3>
      {!r.evidence.length && <p>No relevant passages retrieved.</p>}
      {r.evidence.map((d) => (
        <details
          id={"source-" + d.id}
          key={d.id}
          open={findings(d.id).length > 0}
        >
          <summary>
            {d.publisher} · {d.title}
          </summary>
          {findings(d.id).map((f, i) => (
            <div key={i}>
              <b>
                {f.relation} · Assertion {f.assertion + 1}
              </b>
              <blockquote>{f.quote}</blockquote>
              <p>{f.reason}</p>
            </div>
          ))}
          <p>{d.text}</p>
          <small>
            {d.mode} · {d.date || "Publication date unknown"} · Retrieved{" "}
            {d.retrieved} · ID {d.id}
          </small>
          <p>
            {d.indicators.join(" · ")} · Indicator score{" "}
            {d.credibility.toFixed(2)}/1
          </p>
          <a href={d.url} target="_blank" rel="noreferrer">
            Original source <ExternalLink size={14} />
          </a>
        </details>
      ))}
      <details>
        <summary>Search queries and limitations</summary>
        {[
          ...r.analysis.queries,
          ...r.limitations,
          ...r.validation_failures.map((x) => x.reason),
        ].map((v, i) => (
          <p key={i}>{v}</p>
        ))}
      </details>
    </article>
  );
}
