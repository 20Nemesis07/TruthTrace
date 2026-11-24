# TruthTrace
SCSE4041 Prompt Engineering · TruthTracers · PE-B25-30 · C22

Enter a public factual claim and click **Verify claim**. TruthTrace finds its own evidence and shows exact quotations, clickable sources, dated provenance, subclaim decisions and limitations. The old manual passage-entry workflow has been replaced.

## Windows
1. Extract the entire ZIP. Open the **TruthTrace** folder and double-click **run.bat** (Windows may display **run**). Install Python 3.10+ with the Windows py launcher first.
2. The launcher creates a virtual environment, installs Python packages and opens a new **.env** next to run.bat in Notepad on first use. If you already have an unexposed Groq key, use AI_PROVIDER=groq and paste it after GROQ_API_KEY=. To use the specified Gemini integration, select AI_PROVIDER=gemini and set GEMINI_API_KEY. Use a free-tier project. Save and close Notepad. Restart the launcher after later edits. Keys stay on the backend.
3. Open http://127.0.0.1:8000 and keep the terminal open. The compiled React frontend is included. Node is only needed for frontend development.

## macOS / Linux
From the extracted TruthTrace directory:
```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp -n .env.example .env
nano .env
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000. In nano save with Ctrl+O, Enter, then exit with Ctrl+X.

## First demonstration
- Select **Offline collection only**, enter **Mars has no rings.** and verify. Inspect the exact NASA quote, open its source, download the JSON report and reopen it under History.
- With your selected provider key configured, clear the offline checkbox. Enter **The RBI’s May 2023 notice declared ₹2000 notes invalid.** The system searches, compares the claim with the dated notice, and may abstain if conflicting or insufficient evidence survives.
- Without a provider key the system can still retrieve, rank and inspect documents. Its explicitly labeled literal comparison is intentionally narrow. An unavailable live model is reported instead of inventing a result.

## Accounts and cost
Use the free tier only. Groq and Gemini are alternative interpreters. The app sends claim and evidence to the selected provider. Wikipedia, Crossref, Europe PMC, PIB RSS, GOV.UK publications and the Indian Prime Minister’s Office profile need no search key. For optional additional discovery with a compatible Groq GPT-OSS model, set GROQ_BROWSER_SEARCH=1 in .env. This makes an extra Groq browser-search request on an uncached search and is off by default. The app reads publisher pages directly to validate quotes. An optional FACTCHECK_API_KEY can enable Google Fact Check Tools in a project with access. Empty keys are fine for the offline demonstration. Rate limits, regional eligibility, provider policy and outages affect coverage. Do not enable paid billing for this project.
- Gemini model and pricing: https://ai.google.dev/gemini-api/docs/pricing
- Groq free plan limits: https://console.groq.com/docs/rate-limits
- Crossref public interface: https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- Europe PMC: https://europepmc.org/RestfulWebService
- PIB feeds: https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1

## Frontend development
Use Node 22 with npm. Keep FastAPI on port 8000. In frontend, run `npm ci`, then `npm run dev`. Open the address printed by Vite. To rebuild the bundled frontend, run `npm run build`.

## Tests and prompt experiments
Run from the project root, with the Python environment active:
```sh
python -m unittest discover -s tests -v
python -m evaluation.evaluate_prompts --limit 3 --repeats 2
```
For all 40 claims use --limit 40. Two repeats require up to 240 provider requests for all three prompt versions. Start small within your own free quota. Runs are sequential and record provider failures. Results are stored in SQLite and timestamped JSON in evaluation/results. Evaluation never silently inserts offline predictions. No live experiment scores ship in this package.

The dataset supplies reviewed reference passages, source URLs, expected labels and reference-conditioned edge cases. It is a small teaching benchmark concentrated on six documents, not an estimate of open-web accuracy. The evaluator pairs each gold document with a distractor and holds passages, model and response schema constant across V1–V3. Its evidence relevance metric measures citation of the designated reference document. Unsupported verdict rate is a proxy using the reference label and citation checks. Consistency is the fraction of repeated cases with identical completed verdicts. Failed calls are counted separately. Production prompts P1–P3 and experiment prompts V1–V3 are separate files.

Architecture and limitations are in docs/ARCHITECTURE.md. API contracts are in docs/API.md and interactive at /docs. Local runtime data goes in data/truthtrace.sqlite3. Keep this unauthenticated classroom application on your own computer.
