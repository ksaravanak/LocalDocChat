import uuid
from pathlib import Path

from app.config import CHUNK_OVERLAP, CHUNK_SIZE, UPLOAD_DIR
from app.database import (
    embedding_to_json,
    get_connection,
    row_to_dict,
    utc_now,
)
from app.services.ollama_service import embed_texts
from app.services.text_extractor import chunk_text, extract_text


def list_documents() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, size_bytes, chunk_count, uploaded_at FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def get_all_chunks() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, d.filename
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            ORDER BY c.document_id, c.chunk_index
            """
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def save_upload(filename: str, content: bytes, mime_type: str | None) -> dict:
    stored_name = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(content)

    text = extract_text(dest, mime_type)
    pieces = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not pieces:
        dest.unlink(missing_ok=True)
        raise ValueError("Could not extract any text from this file.")

    try:
        vectors = embed_texts(pieces)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO documents (filename, stored_name, mime_type, size_bytes, chunk_count, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, stored_name, mime_type, len(content), len(pieces), utc_now()),
        )
        doc_id = cur.lastrowid

        for idx, (piece, vector) in enumerate(zip(pieces, vectors)):
            conn.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, content, embedding)
                VALUES (?, ?, ?, ?)
                """,
                (doc_id, idx, piece, embedding_to_json(vector)),
            )

    return {
        "id": doc_id,
        "filename": filename,
        "chunk_count": len(pieces),
        "size_bytes": len(content),
    }


def delete_document(doc_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stored_name FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return False

        conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    stored = UPLOAD_DIR / row["stored_name"]
    stored.unlink(missing_ok=True)
    return True
