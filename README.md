# PKAI – Personal Knowledge AI Assistant

A **Python-first, LangChain-centric AI assistant** with **RAG**, **agentic reasoning**, and **MCP-style tools**. Supports **OpenAI** and **Google Gemini** and runs as one service (e.g. on Railway).

## Features

- **Dual LLM**: Configure **OpenAI** or **Gemini** via `LLM_PROVIDER`.
- **RAG**: Personal knowledge base over ingested documents (FAISS locally, pgvector on Railway).
- **Explicit tools**: `search_knowledge_base`, `fetch_external_updates`, `create_file_in_drive` (Google Drive), `create_google_task` (Google Tasks).
- **MCP client**: `app/mcp_client` connects to **workspace-mcp** (PyPI) to create files in Google Drive and tasks in Google Tasks.

## Quick start

### 1. Install

This project targets **Python 3.11**. (A `.python-version` file is included for pyenv.)

```bash
python3.11 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure

- **OpenAI**: `OPENAI_API_KEY=...` and `LLM_PROVIDER=openai` (default).
- **Gemini**: `GOOGLE_API_KEY=...` and `LLM_PROVIDER=gemini`.

Optional:

- `ENV=local` (default) or `ENV=railway`
- `OPENAI_MODEL`, `GEMINI_MODEL` to change models

### 3. Run the web app

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and chat. The UI shows when knowledge or tools were used.

### 4. (Optional) Ingest documents

Use the **Ingest** page (link from the home page) or the CLI. Supported sources:

- **Local**: Put `.txt`, `.md`, `.pdf`, or `.docx` in a `documents/` folder at the project root.
- **Google Drive (SDK)**: Uses the Drive API with a service account; set `GOOGLE_DRIVE_CREDENTIALS_PATH`. Share folders with the service account email.
- **Google Drive (OAuth)**: Uses your Google account — full access to your Drive. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` (Web application client), add redirect URI `http://localhost:8000/auth/google/drive/callback` in Google Cloud Console, then use **Connect Google Drive** on the Ingest page once.
- **Google Workspace (MCP)**: Uses the [workspace-mcp](https://pypi.org/project/workspace-mcp/) PyPI package (Docs, Sheets, Drive). No clone or build; install with `pip install workspace-mcp`. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` (Google Cloud OAuth Desktop credentials). OAuth runs on first use.

CLI (local only): `ENV=local OPENAI_API_KEY=... python -m ingestion.ingest_docs`

Local run writes a FAISS index under `data/faiss_index`. The next time you start the app, it will use that index.

### 5. MCP client (Google Drive + Google Tasks)

The app includes an **MCP client** that talks to the **workspace-mcp** PyPI server (stdio) to create files in Google Drive and tasks in Google Tasks. Use it from your own code or scripts:

```python
from app.mcp_client import create_file_in_drive, create_google_task

# Create a file in Drive (optional: folder_id, mime_type)
result = create_file_in_drive("My note.txt", "Hello from PKAI")

# Create a task in Google Tasks (optional: task_list_id, notes, due in RFC 3339)
result = create_google_task("Review DIDs", notes="Check trustee and stewards")
```

Requires `workspace-mcp` (in requirements.txt), `GOOGLE_OAUTH_CLIENT_ID`, and `GOOGLE_OAUTH_CLIENT_SECRET`. OAuth runs on first use of workspace-mcp.

## Project layout

```
├── app/
│   ├── main.py           # FastAPI app
│   ├── agent.py          # LangChain agent
│   ├── llm_factory.py    # OpenAI / Gemini
│   ├── mcp_client.py     # MCP client: workspace-mcp → Drive file + Google Task
│   ├── schemas.py
│   ├── tools/            # MCP-style tools
│   ├── rag/              # Retriever, vector store, embeddings
│   └── templates/
├── ingestion/
│   ├── ingest_docs.py
│   ├── load_vectorstore.py
│   └── chunk_and_embed.py
├── requirements.txt
├── Dockerfile
└── README.md
```

## Railway

- Set `ENV=railway` and `DATABASE_URL` (Postgres with pgvector).
- Deploy this repo; the Dockerfile runs `uvicorn app.main:app`.
- Run ingestion (e.g. one-off job) with `ENV=railway` and `DATABASE_URL` to populate pgvector.
- **Google Drive (SDK) ingest:** `secrets/*.json` is not in the image. Set **`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`** to the full service account JSON, or set **`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_B64`** to the file’s contents encoded with `base64` (no newlines), which avoids PEM/`private_key` newline mangling in some dashboards. Alternatively mount the key file and set `GOOGLE_APPLICATION_CREDENTIALS`. Unset `GOOGLE_DRIVE_CREDENTIALS_PATH` if the file is not in the image.

## License

MIT.
