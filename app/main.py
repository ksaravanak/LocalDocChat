from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import (
    ALLOWED_EXTENSIONS,
    APP_PASSWORD,
    CHAT_MODEL,
    EMBEDDING_MODEL,
    HOST,
    MAX_UPLOAD_MB,
    PORT,
    PUBLIC_ACCESS,
)
from app.database import init_db
from app.services.document_service import (
    delete_document,
    get_all_chunks,
    list_documents,
    save_upload,
)
from app.services.ollama_service import (
    answer_question,
    check_ollama,
    retrieve_relevant_chunks,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="LocalDocChat", version="1.0.0")

_cors_origins = ["*"] if PUBLIC_ACCESS else [
    f"http://{HOST}:{PORT}",
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not PUBLIC_ACCESS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[dict] = Field(default_factory=list)


class LoginRequest(BaseModel):
    password: str


def require_auth(authorization: str | None = Header(default=None)) -> None:
    if not APP_PASSWORD:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    if token != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    status = check_ollama()
    if not status.get("reachable"):
        print("WARNING: Ollama is not running. Start it with: ollama serve")
    elif not status.get("chat_ready"):
        print(f"WARNING: Chat model not found. Run: ollama pull {CHAT_MODEL}")
    elif not status.get("embed_ready"):
        print(f"WARNING: Embedding model not found. Run: ollama pull {EMBEDDING_MODEL}")
    if PUBLIC_ACCESS and not APP_PASSWORD:
        print("WARNING: APP_PASSWORD is empty. Set a password before sharing the URL.")


@app.get("/api/health")
def health():
    ollama = check_ollama()
    return {
        "status": "ok",
        "auth_required": bool(APP_PASSWORD),
        "ollama": ollama,
        "chat_model": CHAT_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "public_access": PUBLIC_ACCESS,
        "fully_local": True,
    }


@app.post("/api/login")
def login(body: LoginRequest):
    if not APP_PASSWORD:
        return {"token": "public", "auth_required": False}
    if body.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": APP_PASSWORD, "auth_required": True}


@app.get("/api/documents")
def documents(_: None = Depends(require_auth)):
    return {"documents": list_documents()}


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    _: None = Depends(require_auth),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_UPLOAD_MB} MB limit")

    ollama = check_ollama()
    if not ollama.get("reachable"):
        raise HTTPException(status_code=503, detail="Ollama is not running. Start: ollama serve")
    if not ollama.get("embed_ready"):
        raise HTTPException(
            status_code=503,
            detail=f"Embedding model missing. Run: ollama pull {EMBEDDING_MODEL}",
        )

    try:
        result = save_upload(file.filename, content, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"document": result}


@app.delete("/api/documents/{doc_id}")
def remove_document(doc_id: int, _: None = Depends(require_auth)):
    if not delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}


@app.post("/api/chat")
def chat(body: ChatRequest, _: None = Depends(require_auth)):
    ollama = check_ollama()
    if not ollama.get("reachable"):
        raise HTTPException(status_code=503, detail="Ollama is not running. Start: ollama serve")
    if not ollama.get("chat_ready"):
        raise HTTPException(
            status_code=503,
            detail=f"Chat model missing. Run: ollama pull {CHAT_MODEL}",
        )

    chunks = get_all_chunks()
    try:
        relevant = retrieve_relevant_chunks(body.message, chunks)
        answer = answer_question(body.message, relevant, body.history)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "answer": answer,
        "sources": [
            {"filename": c["filename"], "chunk_index": c["chunk_index"]}
            for c in relevant
        ],
    }


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
