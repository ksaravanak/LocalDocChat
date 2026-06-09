# LocalDocChat

Self-hosted document Q&A — upload files, ask questions, get answers. **100% local** using [Ollama](https://ollama.com) and **Qwen**. No cloud API keys, no data sent to external AI services.

```
┌─────────────┐     upload      ┌──────────────────┐     local AI    ┌─────────┐
│   Browser   │ ──────────────► │  LocalDocChat    │ ──────────────► │ Ollama  │
│  (anywhere) │ ◄────────────── │  (your server)   │ ◄────────────── │  Qwen   │
└─────────────┘     answers     └──────────────────┘                 └─────────┘
                                        │
                                        ▼
                                 data/uploads/
                                 (your files)
```

## Features

- Upload **PDF, DOCX, TXT, MD, CSV** (up to 50 MB)
- Chat interface with **source citations**
- Documents stored on **your server** (`data/uploads/`)
- **RAG** — retrieves relevant passages before answering
- Optional **password protection**
- **Public URL** support via Cloudflare tunnel (access from phone or outside office)
- Fully **self-hostable**

## Requirements

| Requirement | Notes |
|-------------|--------|
| [Ollama](https://ollama.com) | Must be installed and running |
| Python 3.10+ | For the web server |
| `qwen2.5:7b-instruct` | Chat / answers |
| `nomic-embed-text` | Document search embeddings |

## Quick start

### 1. Install Ollama models (one time)

Double-click **`Setup-Ollama-Models.bat`**, or:

```powershell
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
```

### 2. Configure (optional)

```powershell
copy .env.example .env
```

Edit `.env` if you need to change the port, models, or set a password.

### 3. Run locally

Double-click **`Run-LocalDocChat.bat`**, or:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

Open **http://127.0.0.1:8090**

## Public access (share with others)

Use this when you need access **outside your network** (mobile data, another office, etc.).

> **Do not** use `http://ServerName:8090` from outside — that only works on the same Wi‑Fi.

1. Set a password in `.env`:
   ```
   APP_PASSWORD=your-secure-password
   ```
2. Double-click **`Run-LocalDocChat-Public.bat`**
3. Wait ~15 seconds, then copy the URL from the terminal or **`public-url.txt`**
   - Format: `https://something.trycloudflare.com`
4. **Keep the terminal window open** while using the app

Ollama and your documents stay on your machine — the tunnel only forwards the web UI.

The public URL **changes each time** you restart the public launcher.

## Project structure

```
LocalDocChat/
├── app/
│   ├── main.py              # FastAPI server
│   ├── config.py            # Settings from .env
│   ├── database.py          # SQLite index
│   ├── services/
│   │   ├── ollama_service.py
│   │   ├── document_service.py
│   │   └── text_extractor.py
│   └── static/              # Web UI
├── data/
│   ├── uploads/             # Uploaded files (not in git)
│   └── documents.db         # Search index (not in git)
├── Run-LocalDocChat.bat
├── Run-LocalDocChat-Public.bat
├── Setup-Ollama-Models.bat
├── run_public.py
├── requirements.txt
└── .env.example
```

## Where files are stored

| Item | Location |
|------|----------|
| Uploaded documents | `data/uploads/` |
| Text index & embeddings | `data/documents.db` |
| Config & secrets | `.env` (never commit to git) |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API address |
| `CHAT_MODEL` | `qwen2.5:7b-instruct` | Qwen model for answers |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model for search |
| `APP_PASSWORD` | empty | Login password (recommended for public access) |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` for LAN) |
| `PORT` | `8090` | Web server port |
| `PUBLIC_ACCESS` | `false` | Set automatically by public launcher |

## How it works

1. **Upload** — file saved to `data/uploads/`, text extracted
2. **Index** — text split into chunks, embedded locally via Ollama
3. **Ask** — your question is embedded, most relevant chunks retrieved
4. **Answer** — Qwen responds using only those excerpts and cites source filenames

## Security

- Documents never leave your server (except through the web UI you expose)
- AI inference runs locally via Ollama — no third-party AI API
- Set `APP_PASSWORD` before sharing a public URL
- Never commit `.env` or `data/` to git (already in `.gitignore`)

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **Ollama offline** | Start Ollama app or run `ollama serve` |
| **Model missing** | Run `Setup-Ollama-Models.bat` |
| **Slow answers** | Normal on CPU; a GPU speeds up Qwen a lot |
| **Upload fails on PDF** | PDF must contain selectable text (not scanned images only) |
| **Public URL not working** | Restart `Run-LocalDocChat-Public.bat`, use new URL from `public-url.txt` |
| **Can't access from outside** | Use the `https://....trycloudflare.com` link, not a local IP |

## License

Use and modify freely for your team or organization.
