import React, { useEffect, useState } from "react";
import { api } from "../services/api";
export default function History({ open }) {
  const [q, setQ] = useState(""),
    [rows, setRows] = useState([]),
    [err, error] = useState("");
  useEffect(() => {
    let active = true;
    api("history?q=" + encodeURIComponent(q))
      .then((x) => {
        if (active) {
          setRows(x);
          error("");
        }
      })
      .catch((e) => active && error(e.message));
    return () => {
      active = false;
    };
  }, [q]);
  return (
    <section className="card">
      <h2>Verification history</h2>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search past claims"
        aria-label="Search past claims"
      />
      {err && <p role="alert">{err}</p>}
      {rows.map((r) => (
        <button className="entry" key={r.id} onClick={() => open(r.id)}>
          <b>{r.verdict}</b> {r.claim}
          <small>{new Date(r.date).toLocaleDateString()}</small>
        </button>
      ))}
      {!rows.length && !err && <p>No matching verifications.</p>}
    </section>
  );
}
