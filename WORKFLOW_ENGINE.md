# Workflow Engine — Design & How It Works

This document explains how the workflow engine in this repository works, how its pieces fit together, and how to extend or debug it. It maps concepts to files present in `e:\Workflow Automation p4 - Copy\backend` so you can quickly find the implementation.

## High-level overview

The workflow engine is responsible for executing user-defined automation flows composed of nodes. Each node represents an operation (e.g., call GitHub, read a file, call an AI model, transform text). The engine orchestrates node execution, handles inputs/outputs, manages state (memory), and integrates with external providers (GitHub, Airtable, Google Drive, AI providers, etc.).

Core responsibilities:
- Schedule and execute nodes in the correct order
- Pass data (outputs) from one node to the next
- Persist execution state and results when needed
- Handle retries, failures, and timeouts
- Provide hooks that integration nodes use to call external APIs

## Key components and files

- `node_handlers.py` — Central engine logic that executes nodes and dispatches to specific node types.
- `integration_node_handlers.py` — Integration-specific handlers and shared plumbing for provider nodes.
- `new_node_handlers.py` / `ai_node_handlers.py` — Node implementations for AI, specialized tasks and newer node types.
- `ai_task_executor_node.py` / `ai_providers_node.py` — Orchestrate AI-provider specific calls, batching, and model selection.
- `github_node.py`, `hubspot_node.py`, `google_drive_node.py`, `airtable_*` — Provider integration implementations.
- `database.py` — Persistence helpers (MongoDB), used to store workflows, node runs, and any persistent memory.
- `chat_memory_node.py` / `file_save_node.py` — Implement memory and file persistence nodes used across flows.
- `file_transformer_node.py` / `document_to_text_node.py` — Helpers to transform and extract text from files.
- `main.py` / `main_minimal.py` / `simple_server.py` — Entry points that initialize DB, load config, and start the service or API used to trigger workflows.
- `config.py` — Centralized configuration loader (env variables, defaults).
- `oauth_verification.py` / `fix_airtable_auth.py` — OAuth helpers used by provider nodes.

## Data model and terminology

- Workflow: A user-defined graph/list of nodes connected to express the automation.
- Node: A single operation (integration call, AI call, transform, conditional, etc.). Each node has `params` and may accept inputs and produce outputs.
- Run / Execution Context: A single instance of a workflow run. Contains runtime variables, node outputs, and metadata (start/end time, status).
- Memory / Store: Persistent storage for long-running or stateful workflows (often in MongoDB or Redis). Some nodes persist outputs for later runs.

## Execution flow (runtime)

1. Trigger: A workflow run starts via an API call, a webhook, or a scheduled trigger. The trigger handler prepares an execution context and initial inputs.
2. Resolve Next Node(s): The engine evaluates which node(s) are ready to run (based on dependency edges and previous outputs).
3. Execute Node: The engine calls the node handler for that node type (e.g., `github_node`, `ai_node_handlers`) passing in runtime inputs and node params.
4. Wait / Async: If the node performs asynchronous I/O (HTTP to an API or model call), the engine will await completion. Some nodes may spawn background tasks.
5. Normalize Output: The node returns a normalized output object. The engine records this in the execution context and optionally persists it.
6. Continue: The engine marks the node as complete and schedules downstream node(s). Repeat until no nodes remain.
7. Finalize: The engine marks the workflow run as finished (success/failure), persists run metadata, and emits events/notifications.

## Node lifecycle and handlers

Each node execution follows a common lifecycle, implemented in `node_handlers.py` and the handler modules:

1. Validate params — ensure required params exist (ownerName, repoName, etc.).
2. Prepare inputs — merge runtime variables with configured node params.
3. Authorize — ensure the run has valid credentials (OAuth token present or API key) for integration nodes.
4. Call provider API / execute logic — perform the core operation.
5. Handle provider errors — parse provider errors and map to engine-level error codes.
6. Return output or error — outputs are objects stored in execution context.

Handlers are implemented with the following pattern (pseudo):

```python
# node_handlers.py (conceptual)
inputs = resolve_inputs(node, run_context)
try:
    result = specific_node_handler.execute(inputs, node.params)
    persist_output(node, result)
    mark_node_success(node)
except ProviderError as e:
    mark_node_failure(node, e)
    if node.params.get('retry'): schedule_retry(node)
```

Provider-specific handlers (`github_node.py`, etc.) wrap provider API calls, handle rate-limit, and refresh tokens when necessary.

## Error handling & retries

- Short-term network errors typically trigger transient retry logic inside node handlers.
- Provider errors (4xx) are surfaced to the run and usually cause the node to fail without retry.
- The engine tracks failure reason and logs errors to `smart_database.log` (or configured logger).
- Some nodes accept `retry` and `backoff` params; the engine scheduler uses these to re-queue node runs.

## Persistence and state

- Execution metadata and node outputs are typically stored in MongoDB via `database.py` helpers.
- Chat and conversation state may be stored via `chat_memory_node.py`.
- Large artifacts (files) may be persisted using the `file_save_node.py` implementations and referenced by id in the DB.

## Concurrency and scaling

- Engine supports multiple parallel node executions (async I/O bound). The server entrypoint (uvicorn or similar) runs worker processes.
- For heavier loads, run multiple worker processes or scale containers horizontally. Shared state (MongoDB/Redis) allows workers to coordinate.

## How OAuth + Credentials are handled

- OAuth flows are implemented by provider modules (see `oauth_verification.py` for helpers).
- Tokens are stored on user records in the database (see `database.py` + `user` related code). Handlers fetch the token for the run to call provider APIs.
- If tokens expire, provider-specific handlers try to refresh or return an explicit token-expired error so the frontend can re-authenticate.

## Adding a new node type — step-by-step

1. Define node params and UI representation in the frontend (node type, form fields).
2. Create a handler inside `new_node_handlers.py` or `integration_node_handlers.py`:
   - Add a function `execute(node, inputs, run_context)` that returns a normalized output dict.
   - Validate required params and input shapes.
3. Register the handler in the central dispatch (`node_handlers.py`) — map type string to handler function.
4. Add tests in `test_node_handler_direct.py` (or create a new test file) covering happy and failure paths.
5. Run `pytest` and start the server to test the new node in an end-to-end workflow.

## Debugging tips

- To reproduce the `ModuleNotFoundError` earlier, try running uvicorn from a different cwd. Fix by running from repo root or adjusting `PYTHONPATH`.
- Enable verbose logs in `config.py` or wherever logging is configured to see provider request/response.
- Use tests under `test_*.py` for quick isolation; many tests are already present (e.g., `test_github_workflow.py`).
- For OAuth issues, inspect the redirect URLs and ensure `FRONTEND_URL` and OAuth app callback URL match exactly.

## Example: simple run trace (read-file node)

1. Trigger run with payload `{ "nodeId": "n1", "inputs": { "ownerName": "me", "repoName": "repo", "fileName": "README.md" } }`.
2. Engine schedules `n1` (type: github/read-file).
3. `node_handlers.py` calls `github_node.read_file(node, inputs)`.
4. `github_node` fetches stored access token for the user from DB, calls GitHub API, decodes base64 content, and returns `{ "content": "..." }`.
5. Engine stores the output and continues to downstream nodes.

## Useful commands (PowerShell)

```powershell
# From backend folder
cd "E:\Workflow Automation p4 - Copy\backend"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
# or, with uvicorn from project root to avoid ModuleNotFoundError
cd "E:\Workflow Automation p4 - Copy"
uvicorn "backend.main:app" --reload --port 8000
```

## Next steps / Recommendations

- If you want one canonical server entrypoint, pick `main.py` and ensure its imports are absolute (so `uvicorn backend.main:app` works from repo root). I can make this change.
- Add small `DEV_RUN.ps1` to standardize dev startup and prevent `ModuleNotFoundError` on Windows.
- Add a short `RUNNING.md` cross-linking the backend and frontend dev steps for new developers.

---

If you'd like, I can now:
- Update `main.py` to ensure import paths are absolute and make it safe to run `uvicorn backend.main:app` from the repo root, and
- Add `DEV_RUN.ps1` in the `backend` folder with the exact PowerShell commands above.

Which do you want me to do next? If both, say "do both" and I'll implement them and run a quick smoke test.