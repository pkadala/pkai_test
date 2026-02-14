"""FastAPI entrypoint: web UI and chat API."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.schemas import ChatRequest, ChatResponse, IngestRequest, IngestResponse
from app.agent import run_agent
from app.ingest_runner import run_ingest
from app.google_oauth import DRIVE_SCOPE, save_drive_tokens
from app import env as env_loader

# Server-side OAuth state store (avoids cookie loss on redirect from Google)
_oauth_states: dict[str, float] = {}
_STATE_TTL_SEC = 600


def _oauth_state_valid(state: str | None) -> bool:
    if not state:
        return False
    now = time.time()
    if state in _oauth_states and (now - _oauth_states[state]) < _STATE_TTL_SEC:
        del _oauth_states[state]
        return True
    # Clean old entries
    for s, t in list(_oauth_states.items()):
        if now - t >= _STATE_TTL_SEC:
            del _oauth_states[s]
    return False


app = FastAPI(
    title="PKAI",
    description="Personal Knowledge AI Assistant",
    version="1.0.0",
)

# Optional static assets
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    """Process a user message through the LangChain agent and return a grounded response."""
    try:
        return run_agent(body.message, chat_history=None)
    except Exception as e:
        err_msg = str(e).lower()
        if "resource_exhausted" in err_msg or "429" in err_msg or "quota" in err_msg:
            raise HTTPException(
                status_code=429,
                detail="LLM API quota or rate limit exceeded. Try again in a minute, or set LLM_PROVIDER=openai in .env to use OpenAI.",
            ) from e
        if "langchain_google_genai" in type(e).__module__ or "generativeai" in err_msg:
            raise HTTPException(
                status_code=503,
                detail=f"Gemini API error: {str(e)[:400]}",
            ) from e
        raise


@app.get("/auth/google/drive")
async def auth_google_drive_start():
    """Redirect to Google OAuth consent for Drive access. Requires GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."""
    if not env_loader.google_oauth_client_id() or not env_loader.google_oauth_client_secret():
        return RedirectResponse(url="/ingest?error=oauth_not_configured", status_code=302)
    from google_auth_oauthlib.flow import Flow

    client_config = {
        "web": {
            "client_id": env_loader.google_oauth_client_id(),
            "client_secret": env_loader.google_oauth_client_secret(),
            "redirect_uris": [env_loader.google_oauth_redirect_uri()],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=DRIVE_SCOPE, redirect_uri=env_loader.google_oauth_redirect_uri())
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _oauth_states[state] = time.time()
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(key="oauth_state", value=state, max_age=600, httponly=True, samesite="lax", path="/")
    return response


@app.get("/auth/google/drive/callback")
async def auth_google_drive_callback(request: Request, state: str | None = None, code: str | None = None):
    """Exchange OAuth code for tokens and store them; redirect back to Ingest."""
    if not code:
        return RedirectResponse(url="/ingest?error=no_code", status_code=302)
    # Validate state via server-side store (cookie often missing after redirect from Google)
    if not _oauth_state_valid(state):
        return RedirectResponse(url="/ingest?error=invalid_state", status_code=302)
    if not env_loader.google_oauth_client_id() or not env_loader.google_oauth_client_secret():
        return RedirectResponse(url="/ingest?error=oauth_not_configured", status_code=302)
    from google_auth_oauthlib.flow import Flow

    client_config = {
        "web": {
            "client_id": env_loader.google_oauth_client_id(),
            "client_secret": env_loader.google_oauth_client_secret(),
            "redirect_uris": [env_loader.google_oauth_redirect_uri()],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=DRIVE_SCOPE, redirect_uri=env_loader.google_oauth_redirect_uri())
    flow.oauth2session._state = state
    try:
        flow.fetch_token(code=code)
        save_drive_tokens(flow.credentials)
    except Exception:
        return RedirectResponse(url="/ingest?error=token_exchange_failed", status_code=302)
    response = RedirectResponse(url="/ingest?connected=1", status_code=302)
    response.delete_cookie("oauth_state", path="/")
    return response


@app.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request) -> HTMLResponse:
    """Serve the ingest documents page."""
    connected = request.query_params.get("connected")
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "ingest.html",
        {"request": request, "drive_oauth_connected": connected == "1", "drive_oauth_error": error},
    )


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_documents(body: IngestRequest | None = None) -> IngestResponse:
    """Run document ingestion (load, chunk, embed, persist). Source: local | gdrive_sdk | workspace_mcp."""
    return run_ingest(body)


@app.get("/health")
async def health() -> dict:
    """Health check for Railway/deployment."""
    return {"status": "ok", "service": "pkai"}
