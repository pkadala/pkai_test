# Personal Knowledge AI Assistant (PKAI)

A **Python-first, LangChain-centric AI assistant** that demonstrates **Retrieval-Augmented Generation (RAG)**, **agentic reasoning**, and **explicit tool invocation (MCP-style)** — deployed as **one artifact on Railway**.

This project is intentionally designed to **showcase LangChain agent capabilities**, not frontend UX polish.

---

## 1. Overview

The Personal Knowledge AI Assistant (PKAI) is a request-driven AI system that helps users reason over their personal knowledge using a Python LangChain agent.  
The system emphasizes clarity, explainability, and architectural correctness over UI sophistication.

---

## 2. Goals and Non-Goals

### Goals
- Showcase **Python LangChain agent design**
- Demonstrate **RAG as a first-class capability**
- Make **tool invocation explicit and explainable**
- Support **local development and cloud deployment** seamlessly
- Deploy as **one service from one GitHub repository**

### Non-Goals
- UX polish or frontend frameworks
- Autonomous or background agents
- Multi-tenant or production-scale features
- Complex CI/CD pipelines or microservices

> This is an **agent architecture demo**, not a product UI demo.

---

## 3. High-Level System Flow

1. User submits a query
2. LangChain agent reasons about the request
3. Relevant personal knowledge is retrieved (RAG)
4. Explicit tools are invoked when required
5. Results are synthesized into a grounded response
6. Any state-changing action requires user confirmation

The system is **agentic but not autonomous**.

---

## 4. Core Capabilities

### 4.1 Knowledge Ingestion
- Documents ingested using LangChain loaders
- Content chunked and embedded
- Embeddings written to the active vector store

**Execution model**
- Local: ingest on startup or via script
- Railway: ingest once and persist

---

### 4.2 Retrieval-Augmented Generation (RAG)
- Agent retrieves relevant document chunks per query
- All responses are grounded in retrieved content
- Retrieval is explicit and traceable

---

### 4.3 Agentic Reasoning
- LangChain agent is the central orchestrator
- Agent decides:
  - when to retrieve
  - when to invoke tools
  - how to synthesize results
- Execution is request-scoped

---

### 4.4 Tool Invocation (MCP-Style)
Tools are:
- Explicit
- Named
- Schema-defined
- Invoked intentionally by the agent

Example tools:
- `search_knowledge_base`
- `fetch_external_updates`
- `save_artifact`
- `create_task` (optional)

---

### 4.5 Human-in-the-Loop
- Any state-changing action:
  - must be proposed by the agent
  - must be explicitly confirmed by the user
- No silent writes
- No autonomous execution

---

## 5. Vector Store Strategy (Environment-Aware)

The vector store implementation changes by environment, while **agent logic remains unchanged**.

| Environment | Vector Store | Characteristics |
|-----------|-------------|----------------|
| Local | In-memory FAISS | Fast, ephemeral |
| Railway | PostgreSQL + pgvector | Persistent, durable |

**Design rule:**  
The agent depends only on a **Retriever interface**, not on a specific vector store implementation.

---

## 6. Non-Functional Requirements

### Deployment
- One GitHub repository
- One Railway service
- One Docker image
- One running container

### Runtime
- Long-running Python service
- Stateless per request (except vector store)
- FastAPI entrypoint

### Explainability
The UI must clearly indicate:
- when personal knowledge was used
- when tools were invoked
- why actions were suggested

---

## 7. Technology Stack

### Runtime
- Python 3.11
- FastAPI
- Uvicorn

### Agent & AI
- LangChain (Python)
- OpenAI-compatible LLM provider

### Vector Stores
- FAISS (local, in-memory)
- PostgreSQL + pgvector (Railway)

### UI
- Jinja2 (server-side templates)
- Tailwind CSS (CDN)
- No Node.js
- No frontend build pipeline

### Deployment
- Docker
- Railway
- GitHub → Railway direct deploy

---

## 8. Architecture Principles

- Python-first
- Agent logic > UI
- Explicit over implicit
- Agentic ≠ autonomous
- One repo, one service, one artifact
- Environment-driven configuration

---

## 9. Project Structure

```text
pkai-langchain-demo/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── agent.py                 # LangChain agent
│   ├── schemas.py               # Pydantic models
│   │
│   ├── tools/                   # MCP-style tools
│   │   ├── rag_tool.py
│   │   ├── external_tool.py
│   │   └── action_tool.py
│   │
│   ├── rag/
│   │   ├── retriever.py
│   │   ├── vectorstore_factory.py
│   │   └── embeddings.py
│   │
│   ├── templates/
│   │   └── index.html            # Jinja2 UI
│   │
│   └── static/                   # optional assets
│
├── ingestion/
│   ├── ingest_docs.py
│   ├── chunk_and_embed.py
│   └── load_vectorstore.py
│
├── requirements.txt
├── Dockerfile
├── README.md
└── .gitignore
```

---

## 10. Configuration

### Environment Selector
```bash
ENV=local | railway
```

### Required Environment Variables
```bash
OPENAI_API_KEY=your_key_here
```

### Railway-Only
```bash
DATABASE_URL=postgres://...
```

---

## 11. Deployment (Railway)

1. Push this repository to GitHub
2. Create a new Railway project
3. Deploy from GitHub
4. Railway builds the Docker image
5. FastAPI service starts automatically
6. A public URL is exposed

**Ingestion**
- Local: automatic or manual
- Railway: controlled, one-time execution

---

## 12. How to Describe This Project

### One-Line Description
> A Python LangChain–based Personal Knowledge AI Assistant that demonstrates RAG and tool-driven agentic reasoning, deployed as a single Railway service.

### Architecture Summary
> The UI, LangChain agent, tools, and RAG runtime are deployed together as one artifact. The vector store switches from in-memory locally to Postgres in Railway without changing agent logic.

---

## 13. Final Locked Decisions

- Railway deployment
- Python LangChain agent as the core
- FastAPI + Jinja2 + Tailwind CDN UI
- In-memory vector store locally
- PostgreSQL + pgvector in Railway
- One repository, one artifact, one service

---

## 14. Conclusion

This project intentionally balances **technical credibility, simplicity, and explainability**.  
It mirrors real enterprise agent patterns while remaining easy to deploy, understand, and extend.

The result is a **clean, defensible, Python-first LangChain agent demo**.
