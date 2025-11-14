## BizRefine NLP Word Add-in

BizRefine is a Word task-pane add-in backed by a Flask server that assists business writers with four NLP workflows:

- **Acronym expansion** – scans selection text, expands known acronyms using the local `abbreviations_local.json`, and calls Gemini when a meaning is missing.
- **Citation formatter (placeholder)** – endpoint is wired but currently returns a pass-through value until the team finishes `citations.py`.
- **Context-aware rewriting** – sends the passage to Gemini and returns professional/concise/simpler alternatives.
- **Cross-section consistency** – runs every sentence pair through a DistilBERT NLI pipeline plus numeric heuristics, optionally requesting Gemini to fix detected contradictions.

The backend exposes REST routes (`/process`, `/upload`) and serves the front-end assets in `static/`. The Office manifest (`manifest.xml`) points Word to `static/taskpane.html`, which hosts the Office.js client (`taskpane.js`, `taskpane.css`) that talks to the Flask API.

---

### 1. Prerequisites

- Python 3.9 (the `.bizrefine` virtualenv uses 3.9.6)
- pip
- A Google Gemini API key with access to `gemini-2.5-flash-preview-09-2025`
- Microsoft Word (desktop) with sideloading enabled for task-pane add-ins

---

### 2. Local setup

```bash
# from the repo root
python3 -m venv .bizrefine
source .bizrefine/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` next to `app.py` and add your Gemini credentials:

```
GEMINI_API_KEY=your-key-here
```

Notes:
- `requirements.txt` already includes Flask, Flask-CORS, requests, Hugging Face transformers/torch, nltk, python-docx, numpy, python-dotenv.
- The first consistency run will download the `typeform/distilbert-base-uncased-mnli` weights and required NLTK data (`punkt`, `wordnet`, etc.).
- `abbreviations_local.json` acts as a cache; ship it with the repo so teammates share learned expansions.

---

### 3. Running the backend

```bash
source .bizrefine/bin/activate
python app.py
```

This launches Flask’s dev server on `http://127.0.0.1:5001` (debug mode on). Endpoints:

- `/` – serves the task pane UI
- `/process` – POST JSON `{ action, text, style? }`
- `/upload` – POST `.docx` file form-data to convert to text

The server logs will show Gemini calls and consistency analysis progress.

---

### 4. Using the Word add-in

1. Start Word (desktop) and open any document.
2. Go to **Insert → My Add-ins → Shared Folder / Upload My Add-in** (exact wording varies by platform).
3. Browse to `manifest.xml` in this repo and load it. Word will now trust the localhost URLs defined inside.
4. The “BizRefine Add-in” task pane should appear. If not, open it from **Home → Add-ins**.
5. Highlight some text in the document and choose one of the actions:
   - **Expand** pulls `/process` with `action=expand`, replaces the selection (optional checkbox) with the expanded version, and reports acronyms it still could not resolve.
   - **Citations** currently echoes the text; it is a placeholder until `citations.py` is implemented.
   - **Rewrite** displays professional/concise/simpler rewrites returned by Gemini.
   - **Consistency** sends the entire document (or uploaded `.docx`) through `consistency_model.py`, summarizes contradictions, and—if issues exist—asks Gemini for a corrected draft.
6. Use the **Summary/Raw JSON** tabs to inspect the structured responses.

If Word cannot reach the backend, confirm `python app.py` is still running and that your firewall allows localhost traffic.

---

### 5. Project structure (high level)

- `app.py` – Flask application, routes, docx ingest helper.
- `acroynom.py` – local acronym dictionary + Gemini-backed fallback.
- `consistency_model.py` – NLI pipeline plus numeric heuristics for contradiction detection.
- `rewrite_model.py` – Gemini helpers for rewrite and conflict resolution flows.
- `static/` – Office task pane UI (`taskpane.html`, `taskpane.js`, `taskpane.css`, icons).
- `manifest.xml` – Office add-in manifest pointing Word to the local dev server.
- `abbreviations_local.json` – seed/custom acronym expansions persisted between runs.

---

### 6. Troubleshooting

- **`ModuleNotFoundError`** – ensure the virtual environment is activated and dependencies installed.
- **`ERROR: GEMINI_API_KEY environment variable not set`** – confirm `.env` exists and restart the server so `python-dotenv` reloads it.
- **`NotOpenSSLWarning`** – macOS’ system Python uses LibreSSL; it’s harmless for local development.
- **Uvicorn TypeError** – the project now relies on Flask’s built-in server; run `python app.py`, not `uvicorn`.
- **Word can’t load add-in** – verify manifest URL (`http://127.0.0.1:5001`) matches the server host/port and that Word trusts HTTP sideloading (macOS Word accepts HTTP on localhost).

---

### 7. Next steps / contributions

- Finish `citations.py` to enable the citation formatter endpoint.
- Add automated tests around acronym caching and consistency heuristics.
- Consider packaging the backend as a Docker image for easier team deployment.

Once you’re happy with changes, commit and push:

```bash
git add .
git commit -m "Add README and docs for BizRefine add-in"
git push origin <branch>
```

