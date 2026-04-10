"""FastAPI entrypoint: web UI and chat API."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.schemas import (
    AgentResponse,
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    ToolInvocation,
)
from app.agent import run_agent
from app.ingest_runner import run_ingest
from app.index_service import delete_index, get_indexed_stats

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PKAI",
    description="Personal Knowledge AI Assistant",
    version="1.0.0",
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _get_thread_id(request: Request) -> str:
    thread_id = request.cookies.get("pkai_thread_id")
    if not thread_id:
        thread_id = str(uuid4())
    return thread_id


@app.get("/", response_class=HTMLResponse)
async def ask_page(request: Request) -> HTMLResponse:
    """Main ask UI (pkai-style)."""
    return templates.TemplateResponse(request, "ask.html", {})


@app.post("/query", response_class=HTMLResponse)
async def query_form(request: Request, query_text: str = Form(..., alias="query")):
    """Form POST chat (server-rendered response)."""
    thread_id = _get_thread_id(request)
    try:
        result = run_agent(query_text, chat_history=None)
        knowledge_used = result.used_knowledge
        action_proposed = result.action_proposed
        tools_simple = result.tools_invoked
        response = templates.TemplateResponse(
            request,
            "ask.html",
            {
                "query": query_text,
                "response": result.response,
                "knowledge_used": knowledge_used,
                "tools_invoked": tools_simple,
                "reasoning_steps": result.reasoning_steps,
                "action_proposed": action_proposed,
            },
        )
        if not request.cookies.get("pkai_thread_id"):
            response.set_cookie(key="pkai_thread_id", value=thread_id, max_age=86400 * 30)
        return response
    except Exception as e:
        logger.exception("Query failed: %s", e)
        err_msg = str(e).strip() or f"{type(e).__name__}"
        err_response = templates.TemplateResponse(
            request,
            "ask.html",
            {
                "query": query_text,
                "response": f"Error: {err_msg}",
                "knowledge_used": False,
                "tools_invoked": [],
                "reasoning_steps": [],
                "action_proposed": False,
                "error": err_msg,
            },
        )
        if not request.cookies.get("pkai_thread_id"):
            err_response.set_cookie(key="pkai_thread_id", value=thread_id, max_age=86400 * 30)
        return err_response


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    """JSON chat API (includes reasoning steps and tool records)."""
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


@app.post("/api/query", response_model=AgentResponse)
async def api_query(req: QueryRequest) -> AgentResponse:
    """JSON query API (pkai-style)."""
    result = run_agent(req.query, chat_history=None)
    return AgentResponse(
        response=result.response,
        knowledge_used=result.used_knowledge,
        tools_invoked=[
            ToolInvocation(
                tool_name=r.tool_name,
                tool_input=r.tool_input,
                tool_output=r.tool_output,
            )
            for r in result.tool_records
        ],
        action_proposed=result.action_proposed,
    )


@app.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request) -> HTMLResponse:
    """Ingest documents page with index stats."""
    ingest_status = request.query_params.get("ingest_status")
    ingest_message = request.query_params.get("ingest_message")
    delete_status = request.query_params.get("delete_status")
    delete_message = request.query_params.get("delete_message")
    indexed = get_indexed_stats()
    return templates.TemplateResponse(
        request,
        "ingest.html",
        {
            "ingest_status": ingest_status,
            "ingest_message": ingest_message,
            "delete_status": delete_status,
            "delete_message": delete_message,
            "indexed": indexed,
        },
    )


@app.post("/ingest", response_class=HTMLResponse)
async def ingest_form(
    request: Request,
    source: str = Form(...),
    local_path: str = Form(""),
    folder_id: str = Form(""),
    gdrive_credentials_path: str = Form(""),
    document_ids: str = Form(""),
    recursive: str = Form(""),
):
    """Form POST ingestion (redirect with flash query params)."""
    src = (source or "").strip().lower()
    rec = (recursive or "").lower() in ("true", "1", "yes", "on")

    try:
        if src == "local":
            req = IngestRequest(
                source="local",
                local_path=local_path.strip() or None,
            )
        elif src == "gdrive_sdk":
            req = IngestRequest(
                source="gdrive_sdk",
                folder_id=folder_id.strip() or None,
                document_ids=document_ids.strip() or None,
                recursive=rec,
                gdrive_credentials_path=gdrive_credentials_path.strip() or None,
            )
        else:
            indexed = get_indexed_stats()
            return templates.TemplateResponse(
                request,
                "ingest.html",
                {
                    "ingest_status": "error",
                    "ingest_message": f"Unknown source: {source}",
                    "indexed": indexed,
                },
            )

        out = run_ingest(req)
        indexed = get_indexed_stats()
        if not out.ok:
            return templates.TemplateResponse(
                request,
                "ingest.html",
                {
                    "ingest_status": "error",
                    "ingest_message": out.message,
                    "indexed": indexed,
                },
            )
        msg = out.message
        return RedirectResponse(url=f"/ingest?ingest_status=ok&ingest_message={quote(msg)}", status_code=303)
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        indexed = get_indexed_stats()
        return templates.TemplateResponse(
            request,
            "ingest.html",
            {
                "ingest_status": "error",
                "ingest_message": str(e),
                "indexed": indexed,
            },
        )


@app.post("/ingest/delete", response_class=HTMLResponse)
async def ingest_delete(request: Request):
    """Delete FAISS index."""
    ok, msg = delete_index()
    status = "ok" if ok else "error"
    return RedirectResponse(url=f"/ingest?delete_status={status}&delete_message={quote(msg)}", status_code=303)


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_documents(body: IngestRequest | None = None) -> IngestResponse:
    """JSON ingestion API."""
    return run_ingest(body)


class IngestLocalRequest(BaseModel):
    path: str = Field(..., description="Path to folder or file")


class IngestGoogleDriveRequest(BaseModel):
    folder_id: str | None = None
    document_ids: str | None = None
    recursive: bool = False


@app.post("/api/ingest/local")
async def api_ingest_local(req: IngestLocalRequest) -> dict:
    out = run_ingest(IngestRequest(source="local", local_path=req.path))
    if not out.ok:
        return {"status": "error", "message": out.message, "docs_ingested": 0, "chunks_created": 0}
    # run_ingest doesn't return doc count separately; message contains it
    return {"status": "ok", "message": out.message, "chunks_created": out.chunks_created}


@app.post("/api/ingest/google-drive")
async def api_ingest_google_drive(req: IngestGoogleDriveRequest) -> dict:
    """Ingest via Google Drive API (service account / ADC)."""
    out = run_ingest(
        IngestRequest(
            source="gdrive_sdk",
            folder_id=req.folder_id,
            document_ids=req.document_ids,
            recursive=req.recursive,
        )
    )
    if not out.ok:
        return {"status": "error", "message": out.message, "docs_ingested": 0, "chunks_created": 0}
    return {"status": "ok", "message": out.message, "chunks_created": out.chunks_created}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "pkai", "env": os.getenv("ENV", "local")}

