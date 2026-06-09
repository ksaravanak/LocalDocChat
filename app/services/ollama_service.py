import numpy as np
import httpx

from app.config import (
    CHAT_MODEL,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
    TOP_K_CHUNKS,
)
from app.database import embedding_from_json


def _client() -> httpx.Client:
    return httpx.Client(base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT)


def check_ollama() -> dict:
    try:
        with _client() as client:
            resp = client.get("/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {
                "reachable": True,
                "models": models,
                "chat_ready": any(CHAT_MODEL in m or m == CHAT_MODEL for m in models),
                "embed_ready": any(EMBEDDING_MODEL in m or m == EMBEDDING_MODEL for m in models),
            }
    except Exception as exc:
        return {"reachable": False, "error": str(exc), "models": []}


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    with _client() as client:
        resp = client.post(
            "/api/embed",
            json={"model": EMBEDDING_MODEL, "input": texts},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Ollama embedding failed ({resp.status_code}): {resp.text}. "
                f"Run: ollama pull {EMBEDDING_MODEL}"
            )
        data = resp.json()
        return [list(v) for v in data["embeddings"]]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def retrieve_relevant_chunks(question: str, chunks: list[dict]) -> list[dict]:
    if not chunks:
        return []

    query_vector = embed_texts([question])[0]
    scored: list[tuple[float, dict]] = []

    for chunk in chunks:
        vector = embedding_from_json(chunk["embedding"])
        score = cosine_similarity(query_vector, vector)
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:TOP_K_CHUNKS]]


def answer_question(question: str, context_chunks: list[dict], history: list[dict]) -> str:
    context_block = "\n\n---\n\n".join(
        f"[Source: {c['filename']}]\n{c['content']}" for c in context_chunks
    )

    system = (
        "You are a helpful assistant that answers questions using ONLY the provided "
        "document excerpts. If the answer is not in the documents, say you could not "
        "find it in the uploaded files. Cite the source filename when relevant. "
        "Be concise and accurate."
    )

    if context_block:
        user_prompt = f"Document excerpts:\n\n{context_block}\n\nQuestion: {question}"
    else:
        user_prompt = (
            "No documents have been uploaded yet. Tell the user to upload documents first.\n\n"
            f"Question: {question}"
        )

    messages: list[dict] = [{"role": "system", "content": system}]
    for msg in history[-6:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_prompt})

    with _client() as client:
        resp = client.post(
            "/api/chat",
            json={"model": CHAT_MODEL, "messages": messages, "stream": False},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Ollama chat failed ({resp.status_code}): {resp.text}. "
                f"Run: ollama pull {CHAT_MODEL}"
            )
        data = resp.json()
        return data.get("message", {}).get("content") or "No response generated."
