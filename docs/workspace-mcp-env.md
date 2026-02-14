# Workspace MCP Configuration

This document lists the environment variables used for the workspace-mcp integration (Google Drive & Tasks) in **stdio** vs **streamable-http** mode, and which apply to the **app server** vs the **MCP server**.

---

## Stdio mode (single app server)

The app spawns workspace-mcp as a subprocess. There is no separate MCP server. All variables are set on the **app server**.

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `WORKSPACE_MCP_TRANSPORT` | Optional | Omit or set to `stdio` (default). |
| `WORKSPACE_MCP_OAUTH_REDIRECT_URI` | **Yes** | Full OAuth redirect URI for workspace-mcp (e.g. `http://localhost:8765/oauth2callback`). The app derives port and base URI from this and passes them to the subprocess. |
| `GOOGLE_OAUTH_CLIENT_ID` | **Yes** (for OAuth) | Passed to the subprocess so workspace-mcp can complete Google OAuth. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | **Yes** (for OAuth) | Same. |
| `USER_GOOGLE_EMAIL` | Optional | Passed to the subprocess; used by some tools. |
| `WORKSPACE_MCP_COMMAND` | Optional | Override executable (default: `workspace-mcp` or `python -m workspace_mcp`). |
| `WORKSPACE_MCP_ARGS` | Optional | Override arguments (default: `--tools drive tasks`). |

**Not needed on app server for stdio:** `WORKSPACE_MCP_HTTP_URL`.

---

## Streamable-HTTP mode (app server + MCP server)

The app connects to a separate workspace-mcp service over HTTP. Configure **two** places: the app server and the MCP server.

### App server (PKAI / FastAPI)

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `WORKSPACE_MCP_TRANSPORT` | **Yes** | Must be `streamable-http`. |
| `WORKSPACE_MCP_HTTP_URL` | **Yes** | Full MCP endpoint URL (e.g. `https://mcp-service.up.railway.app/mcp`). |

**Not needed on app server for streamable-http:**  
`WORKSPACE_MCP_OAUTH_REDIRECT_URI`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `USER_GOOGLE_EMAIL` — the app does not use or pass these when using streamable-http.

### MCP server (separate workspace-mcp process)

Set these in the environment of the process that runs `workspace-mcp --transport streamable-http` (e.g. a second Railway service).

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `PORT` or `WORKSPACE_MCP_PORT` | **Yes** | Port the server listens on (Railway often sets `PORT`). |
| `WORKSPACE_MCP_BASE_URI` | **Yes** | Public base URL of this MCP service (e.g. `https://mcp-service.up.railway.app`). |
| `GOOGLE_OAUTH_REDIRECT_URI` | **Yes** | Full redirect URI (e.g. `https://mcp-service.up.railway.app/oauth2callback`). Must match Google Cloud Console. |
| `GOOGLE_OAUTH_CLIENT_ID` | **Yes** | Google OAuth client ID. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | **Yes** | Google OAuth client secret. |
| `USER_GOOGLE_EMAIL` | Optional | For tools that need a user email. |

---

## Quick reference

| Variable | Stdio (app server) | Streamable-http (app server) | Streamable-http (MCP server) |
|----------|--------------------|-----------------------------|-----------------------------|
| `WORKSPACE_MCP_TRANSPORT` | Optional (default stdio) | **Required** (`streamable-http`) | — |
| `WORKSPACE_MCP_HTTP_URL` | Not used | **Required** | — |
| `WORKSPACE_MCP_OAUTH_REDIRECT_URI` | **Required** | Not used | **Required** (or equivalent) |
| `GOOGLE_OAUTH_CLIENT_ID` | **Required** (for OAuth) | Not used | **Required** |
| `GOOGLE_OAUTH_CLIENT_SECRET` | **Required** (for OAuth) | Not used | **Required** |
| `USER_GOOGLE_EMAIL` | Optional | Not used | Optional |
| `PORT` / `WORKSPACE_MCP_PORT` | — | — | **Required** |
| `WORKSPACE_MCP_BASE_URI` | Derived from redirect URI | Not used | **Required** |
| `WORKSPACE_MCP_COMMAND` / `WORKSPACE_MCP_ARGS` | Optional | Not used | Optional |

---

## Local vs production (Railway)

- **Local (stdio):** Use `WORKSPACE_MCP_OAUTH_REDIRECT_URI=http://localhost:8765/oauth2callback`. workspace-mcp runs on the same machine and can open a server on port 8765 for the OAuth callback.
- **Railway (stdio):** A single app process cannot reliably run workspace-mcp’s OAuth server (port conflict). Prefer **streamable-http** with a separate MCP server that has its own public URL and handles the OAuth callback.
- **Railway (streamable-http):** Deploy workspace-mcp as a second service; set its public URL as `WORKSPACE_MCP_BASE_URI` and `GOOGLE_OAUTH_REDIRECT_URI`, and add that redirect URI in Google Cloud Console. On the app service, set only `WORKSPACE_MCP_TRANSPORT=streamable-http` and `WORKSPACE_MCP_HTTP_URL`.
