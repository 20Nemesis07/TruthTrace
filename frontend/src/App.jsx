import React, { useState } from "react";
import {
  Fingerprint,
  Search,
  Library,
  ScanText,
  Quote,
  Network,
  LoaderCircle,
} from "lucide-react";
import Report from "./components/Report";
import History from "./pages/History";
import { api } from "./services/api";
const examples = [
  "Mars has no rings.",
  "The RBI’s May 2023 notice declared ₹2000 notes invalid.",
  "Hot weather prevents people from catching COVID-19.",
];
export default function App() {
  const [page, setPage] = useState("desk"),
    [claim, setClaim] = useState(""),
    [offline, setOffline] = useState(false),
    [report, setReport] = useState(null),
    [stage, setStage] = useState(""),
    [error, setError] = useState("");
  async function verify(e) {
    e.preventDefault();
    setReport(null);
    setError("");
    setStage("Submitting claim");
    try {
      const { job_id } = await api("verify?background=true", {
        claim,
        offline,
      });
      for (;;) {
        const j = await api("jobs/" + job_id);
        if (j.error) throw Error(j.error);
        if (j.done) {
          setReport(await api("history/" + j.report_id));
          break;
        }
        setStage(j.stage);
        await new Promise((resolve) => setTimeout(resolve, 450));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setStage("");
    }
  }
  async function open(id) {
    try {
      setReport(await api("history/" + id));
      setPage("desk");
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <>
      <header>
        <div className="wrap row">
          <div className="brand">
            <Fingerprint />
            TruthTrace
          </div>
          <nav>
            <button
              aria-pressed={page === "desk"}
              onClick={() => setPage("desk")}
            >
              <Search size={17} /> Verify
            </button>
            <button
              aria-pressed={page === "history"}
              onClick={() => setPage("history")}
            >
              <Library size={17} /> History
            </button>
          </nav>
        </div>
      </header>
      <main className="wrap">
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        {page === "history" ? (
          <History open={open} />
        ) : (
          <>
            <div className="hero">
              <div className="kicker">Verification desk</div>
              <h1>
                What’s behind
                <br />
                <em>the claim?</em>
              </h1>
              <p>
                Check a public statement against published evidence and inspect
                the sources behind its verdict.
              </p>
            </div>
            <div className="grid gap-5 md:grid-cols-[1.6fr_1fr] items-start">
              <form className="card" onSubmit={verify}>
                <label htmlFor="claim">Claim to verify</label>
                <textarea
                  id="claim"
                  maxLength={1500}
                  minLength={5}
                  required
                  value={claim}
                  onChange={(e) => setClaim(e.target.value)}
                  placeholder="Paste a statement from a post or message…"
                  rows={4}
                />
                <label className="check">
                  <input
                    type="checkbox"
                    checked={offline}
                    onChange={(e) => setOffline(e.target.checked)}
                  />{" "}
                  Offline collection only
                </label>
                <button
                  className="primary"
                  disabled={!!stage || claim.trim().length < 5}
                >
                  <Search size={17} />
                  Verify claim
                </button>
                <details>
                  <summary>Try an example claim</summary>
                  {examples.map((x) => (
                    <button
                      key={x}
                      className="example"
                      type="button"
                      onClick={() => setClaim(x)}
                    >
                      {x}
                    </button>
                  ))}
                </details>
              </form>
              <aside className="card how">
                <h2>How it works</h2>
                {[
                  [
                    ScanText,
                    "Break down the claim",
                    "Identify assertions, entities and dates.",
                  ],
                  [
                    Network,
                    "Find sources",
                    "Search public indexes and rank passages.",
                  ],
                  [
                    Quote,
                    "Check the evidence",
                    "Validate exact quotes and assess agreement.",
                  ],
                ].map(([Icon, title, body]) => (
                  <div className="step" key={title}>
                    <Icon size={19} />
                    <div>
                      <b>{title}</b>
                      <p>{body}</p>
                    </div>
                  </div>
                ))}
              </aside>
            </div>
            {stage && (
              <div className="card status" role="status">
                <LoaderCircle className="animate-spin" />
                {stage}…
              </div>
            )}
            {report && <Report r={report} />}
          </>
        )}
      </main>
      <footer className="wrap">
        TruthTracers · PE-B25-30 · SCSE4041 · C22
      </footer>
    </>
  );
}
