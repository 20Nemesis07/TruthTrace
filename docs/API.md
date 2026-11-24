# Local REST API
Start the service and open /docs for interactive schemas. JSON input for verify, analyze and search is {"claim":"Mars has no rings.","offline":false}. Set offline to true to disable all outbound requests.
| Method and path | Purpose |
|---|---|
| POST /api/verify | Run all stages and return a persisted report. |
| POST /api/verify?background=true | Start a job and return job_id with HTTP 202. |
| GET /api/jobs/{id} | Current stage, completion flag, report ID or error. Progress reflects work started on the server. |
| POST /api/claims/analyze | Return assertions, topics, qualifiers, queries and limitations. |
| POST /api/evidence/search | Retrieve and rank passages with provenance. |
| POST /api/evidence/validate | Supply report_id and findings containing assertion (zero-based index), evidence_id, quote, relation, and reason. Looks up original passages from the stored report. |
| GET /api/history?q=term | Most recent 100 matching claims. |
| GET /api/history/{id} | Complete report including search queries, evidence, citations, model and limitations. |
| GET /api/health | Selected provider, model and whether a key is present. |
| POST /api/evaluate?limit=3&repeats=2 | Execute and store the three experimental prompts. Requires a key. The CLI supports the full benchmark. |
Invalid inputs return 422, unknown records 404, rate limits 429, and missing experiment credentials 503. Jobs expire after 15 minutes. SQLite retains completed reports. This single-user service is bound to loopback.

Reports use TRUE, FALSE or MISLEADING when the evidence meets the verification rules. Consistent validated quotations with limited corroboration can yield LIKELY TRUE, LIKELY FALSE or POSSIBLY MISLEADING. PARTIAL ASSESSMENT preserves individual findings on compound claims. When a decision is unavailable, the verdict field describes the reason, including NEEDS EVIDENCE, CONFLICTING EVIDENCE or CHECK INCOMPLETE. History and downloads use the same outcomes.
