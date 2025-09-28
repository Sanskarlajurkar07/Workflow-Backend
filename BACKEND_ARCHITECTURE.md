# Backend Architecture & File Map

This document explains how the backend in `e:\Workflow Automation p4 - Copy\backend` is organized, what the important files do, how the different pieces connect (OAuth, database, nodes), how to run it on Windows/PowerShell, and common troubleshooting tips (including the `ModuleNotFoundError: No module named 'backend'` you encountered).

## High-level overview

The backend is a Python-based project (FastAPI/Flask/Plain Python scripts depending on entrypoint used) that contains:

- OAuth and integration logic (GitHub, Google, Airtable, HubSpot, etc.)
- Node handlers that implement actions for the workflow engine
- Utilities for database/storage (MongoDB, Redis, Qdrant references)
- Multiple server entrypoints / scripts for minimal or full servers
- Tests and helpers for local development

There are multiple server entrypoints and helper scripts so different `main`/`quick` modes exist (use the one that matches your needs):

- `main.py` / `main_minimal.py` — main application entrypoints
- `simple_server.py` / `minimal_server.py` / `quick_server.py` — lightweight servers for testing
- `start_backend.bat`, `run_server.bat` — Windows convenience scripts
- `start_server.py` — another start script

Pick a server file and run it from the repository root or from the `backend` folder (see "Common issues").

## Key files and what they do

Below are the most important files and folders. Open them to dive deeper if needed.

- `.env` / `.env.backup`
  - Environment variables used by the backend (DB URIs, OAuth client IDs/secrets, FRONTEND_URL, JWT settings, API keys).

- `config.py`
  - Central configuration loader/utility (reads env, exposes common settings).

- `database.py`
  - Connects to MongoDB and provides DB helper functions.

- `oauth_verification.py`
  - Verification helpers for OAuth flows (token validation, signature checks, webhook verification).

- `github_node.py`, `hubspot_node.py`, `google_drive_node.py`, `airtable_*` files
  - Integration modules that implement repository reads, PRs, issues, and other provider-specific operations.

- `node_handlers.py`, `new_node_handlers.py`, `integration_node_handlers.py`, `ai_node_handlers.py`
  - The actual execution logic for workflow nodes (how the engine executes actions when a node runs).

- `ai_*` files (e.g., `ai_providers_node.py`, `ai_task_executor_node.py`)
  - AI provider wrappers and orchestration logic used by the workflow engine.

- `file_*.py` and `document_to_text_node.py`
  - File handling, document parsing, and text extraction utilities.

- `main.py`, `main_minimal.py`, `simple_main.py`
  - These are entry points that start the HTTP server or the minimal functionality. `main.py` is usually the full server; check inside to confirm.

- `requirements.txt` / `minimal_requirements.txt`
  - Python dependency lists. Use the one appropriate for full or minimal installs.

- `tests` and `test_*.py` files
  - Unit/integration tests. `conftest.py` configures pytest fixtures.

- `start_backend.bat` / `run_server.bat`
  - Windows batch scripts to run the backend. Inspect them to see specific commands used.

## Typical OAuth / Login flow (GitHub example)

1. Frontend redirects the user to the backend OAuth route (e.g., `/auth/github`).
2. Backend redirects to GitHub's authorization URL with `client_id` and callback URL.
3. User authorizes the app on GitHub, GitHub redirects to `/auth/github/callback` with a code.
4. Backend exchanges the code for an access token and stores it (in DB or session).
5. Backend creates a JWT for the frontend (optional) and redirects back to `FRONTEND_URL` with the token.
6. Frontend stores the JWT and uses it for authenticated API calls (e.g., `/github/repos`).

Files that implement that flow are: `oauth_verification.py`, any `auth` routes (e.g., `main.py` or route files), and provider-specific nodes (`github_node.py`).

## How to run locally (Windows / PowerShell)

1. Open PowerShell and navigate to the backend folder:

```powershell
cd "E:\Workflow Automation p4 - Copy\backend"
```

2. Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run as Admin and allow script execution (temporarily):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies (pick the full or minimal requirements):

```powershell
pip install -r requirements.txt
# or for a minimal install
pip install -r minimal_requirements.txt
```

4. Ensure `.env` is configured (copy `.env.backup` if present):

```powershell
copy .env.backup .env
# then edit .env in your editor to add secrets
```

5. Start the server (example using `main.py` or `start_backend.bat`):

```powershell
# Option A: run Python entrypoint directly
python main.py

# Option B: run the batching script (if present)
.
# You can also run named scripts that call uvicorn / hypercorn inside
.
start_backend.bat
```

Some entrypoints use `uvicorn` or `uvicorn` in subprocess; if you see `ModuleNotFoundError` referencing `backend`, it usually means Python import paths are incorrect — see troubleshooting.

## Common issues & fixes

- ModuleNotFoundError: No module named 'backend'
  - Cause: Python was started from a directory where package/module imports expect a package named `backend` or you ran `uvicorn main:app` from a different cwd. The project expects the `backend` package to be importable.
  - Fixes:
    - Run the server from the project root (the folder that makes module imports resolve). Example:
      ```powershell
      cd "E:\Workflow Automation p4 - Copy"
      python -m backend.main
      # or if using uvicorn and main.py expects `main:app`
      uvicorn "backend.main:app" --reload
      ```
    - Alternatively, run the entrypoint directly from within the backend folder (e.g., `python main.py`) if `main.py` uses only relative imports or sets `sys.path`.
    - Avoid starting `uvicorn` with `app` import strings when the module path isn't on `PYTHONPATH`.
    - Add this line at top of `main.py` temporarily (not recommended for production) to help path issues:
      ```python
      import sys, os
      sys.path.append(os.path.dirname(__file__))
      ```

- Environment variables not loaded
  - Ensure `python-dotenv` is installed and `load_dotenv()` is called early (often in `main.py` or `config.py`).

- OAuth callback redirect fails
  - Confirm `FRONTEND_URL` and the OAuth app callback URL registered with the provider (GitHub) match exactly (including port).

## Where to change the OAuth client IDs / secrets

Edit `.env` (or `.env.backup`) values for:

- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
- `AIRTABLE_CLIENT_ID` / `AIRTABLE_CLIENT_SECRET`
- `GITHUB_WORKFLOW_CLIENT_ID` / `GITHUB_WORKFLOW_CLIENT_SECRET`

After changes, restart the server.

## Tests

Run pytest from the backend folder (virtualenv activated):

```powershell
pytest -q
```

If tests depend on environment variables, create a test `.env` file or export the necessary variables in the environment before running.

## Quick dev notes and tips

- There are multiple server modes — open `main.py`, `main_minimal.py`, `simple_server.py` to see which dependencies they load and choose the minimal one if you want a quick start.
- If you want the frontend to run without a backend, consider creating mock endpoints in the frontend or run a tiny local Express/Node server to simulate OAuth redirects.
- For debugging `uvicorn` import errors: run the same import string in an interactive REPL to confirm Python can locate the module (e.g., `python -c "import backend.main as m; print(m)"`).

## Example: Fixing the `ModuleNotFoundError` you posted

Your error shows `ModuleNotFoundError: No module named 'backend'` while `uvicorn` was trying to import the app. One reliable way to start the app is:

1. From the repository root (one level above the `backend` folder):

```powershell
cd "E:\Workflow Automation p4 - Copy"
# run uvicorn and point to backend.main:app
.
uvicorn "backend.main:app" --reload --port 8000
```

2. Or run the file directly inside `backend`:

```powershell
cd "E:\Workflow Automation p4 - Copy\backend"
python main.py
```

If `main.py` contains `if __name__ == "__main__": uvicorn.run("main:app", ...)`, change that to use the full module path when you run from project root or use `uvicorn backend.main:app`.

## Where to look next (mapping to your files)

- Start by opening these to understand control flow:
  - `main.py` or `main_minimal.py`
  - `oauth_verification.py`
  - `node_handlers.py` and `integration_node_handlers.py`
  - `github_node.py`
  - `database.py` and `config.py`

- If you want I can:
  - Add a small `README.md` or `DEV_RUN.md` with exact commands tailored to your environment
  - Update `main.py` to make running with `uvicorn` from the repo root work reliably (adjust imports or `sys.path` safely)
  - Add a small script that sets `PYTHONPATH` automatically before launching to avoid the `ModuleNotFoundError` on Windows

---

If you want, I can now:

- Update `main.py` to be importable as `backend.main` from the repo root (safe change), or
- Add a small `run_dev.ps1` PowerShell script that sets `PYTHONPATH` and starts `uvicorn` correctly.

Which would you prefer? (If you're not sure, I recommend adding the `run_dev.ps1` script — quick and non-invasive.)