import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "documents.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:7b-instruct")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8090"))
PUBLIC_ACCESS = os.getenv("PUBLIC_ACCESS", "").lower() in ("1", "true", "yes")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_CHUNKS = 6
MAX_UPLOAD_MB = 50
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv"}
