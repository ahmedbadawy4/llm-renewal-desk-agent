# Renewal Desk UI (simple)

This is a lightweight, separate UI for the Renewal Desk Agent API. It is a static page with vanilla JS.

## Run
1. Start the API (from the repo root):
   ```bash
   make run-api
   ```
2. Serve the UI (from the repo root):
   ```bash
   python -m http.server 5173 -d ui
   ```
3. Open http://localhost:5173

## Notes
- The UI calls the API at `http://localhost:8000` by default. Change it if needed.
- Use the "Use bundled sample files" button to auto-load the example PDF/CSVs.
- The API enables CORS for localhost ports `5173` and `8080` to allow the UI to call it.
- For Kubernetes, the Helm chart injects the API base URL into `config.js` using `ui.apiBaseUrl`.
- The AI backend selector can switch between `mock` and `ollama` per request.
- The debug trace viewer pulls `/debug/trace/{request_id}` after a run.
