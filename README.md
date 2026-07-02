# Pocket Lawyer API

FastAPI backend for the Pocket Lawyer app — a RAG-powered legal research and document analysis platform. Provides vector search over Indian bare acts and user-uploaded documents using OpenAI embeddings + GPT-4o-mini, with Firebase Authentication.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Expo Client   │────▶│ FastAPI (uvicorn) │────▶│ PostgreSQL 16   │
│ (React Native) │    │ localhost:8000    │    │ + pgvector      │
└──────────────┘     └──────────────────┘     └─────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  OpenAI API   │
                    │  (embeddings + │
                    │   chat)       │
                    └──────────────┘
```

## Features

- **22 Indian Bare Acts** — Pre-ingested with text-embedding-3-small vectors for semantic search
- **Document Upload** — PDF/image upload, text extraction via pdfplumber, chunking, embedding, and RAG storage
- **AI Legal Q&A** — Chat with GPT-4o-mini grounded in retrieved document or law chunks
- **Firebase Auth** — Token-based authentication with email/password and Google Sign-In
- **Background Processing** — Document analysis (extract → chunk → embed) runs asynchronously on upload

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| ASGI Server | uvicorn 0.34 |
| Database | PostgreSQL 16 + pgvector (ivfflat indexes) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.14 |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | OpenAI GPT-4o-mini |
| Auth | Firebase Admin SDK |
| PDF Parsing | pdfplumber 0.11 |
| File Storage | Firebase Storage / local |

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 16 with pgvector extension
- OpenAI API key
- Firebase project with service account credentials

### 1. Clone and environment

```bash
git clone https://github.com/your-org/pocket-lawyer-api.git
cd pocket-lawyer-api
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 2. Database

```bash
# Using Docker (recommended)
docker run -d --name pgvector ^
  -e POSTGRES_USER=user ^
  -e POSTGRES_PASSWORD=password ^
  -e POSTGRES_DB=pocket_lawyer ^
  -p 5432:5432 ^
  pgvector/pgvector:pg16

# Create the extension
docker exec -it pgvector psql -U user -d pocket_lawyer -c "CREATE EXTENSION vector;"
```

### 3. Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/pocket_lawyer` |
| `OPENAI_API_KEY` | OpenAI API key for embeddings + chat |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_CREDENTIALS_JSON` | Full Firebase service account JSON (minified) |

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs at `http://localhost:8000/docs`.

## Ingesting Bare Acts

```bash
# Ingest all PDFs in data/laws/
python -m scripts.ingest_laws

# Ingest a specific act
python -m scripts.ingest_laws --act ipc
python -m scripts.ingest_laws --act "indian contract act"
```

PDFs live in `data/laws/`. See [LAWS_INVENTORY.md](data/laws/LAWS_INVENTORY.md) for the full list and download status.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check |
| `POST` | `/api/v1/auth/register` | Firebase token | Register new user |
| `POST` | `/api/v1/auth/login` | Firebase token | Login / sync user |
| `GET` | `/api/v1/auth/me` | Firebase token | Current user profile |
| `POST` | `/api/v1/documents/upload` | Firebase token | Upload PDF/image (multipart) |
| `GET` | `/api/v1/documents/` | Firebase token | List user's documents |
| `GET` | `/api/v1/documents/{document_id}` | Firebase token | Get document details |
| `DELETE` | `/api/v1/documents/{document_id}` | Firebase token | Soft delete document |
| `POST` | `/api/v1/chat/` | Firebase token | Send message, get AI reply |
| `GET` | `/api/v1/chat/history/{document_id}` | Firebase token | Chat history for a document |
| `GET` | `/api/v1/laws/` | Firebase token | List all acts with chunk counts |
| `GET` | `/api/v1/laws/search?q=` | Firebase token | Semantic search across acts |
| `GET` | `/api/v1/laws/{act_short}` | Firebase token | Get sections for an act |

## Project Structure

```
pocket-lawyer-api/
├── app/
│   ├── main.py                 # FastAPI app, CORS, lifespan, health check
│   ├── core/
│   │   ├── config.py           # Pydantic settings from .env
│   │   ├── database.py         # Async engine, session, init_db
│   │   └── security.py         # Firebase token verification (dev mock fallback)
│   ├── models/
│   │   ├── user.py             # User (id, email, name, created_at)
│   │   ├── document.py         # Document + DocumentChunk (embeddings)
│   │   ├── law.py              # LawChunk (act_name, act_short, section, embedding)
│   │   └── chat.py             # ChatMessage (role, content, sources, conversation_id)
│   ├── api/routes/
│   │   ├── auth.py             # /auth/register, /auth/login, /auth/me
│   │   ├── documents.py        # /documents/upload, /documents/, /documents/{id}
│   │   ├── chat.py             # /chat/, /chat/history/{document_id}
│   │   └── laws.py             # /laws/, /laws/search, /laws/{act_short}
│   └── services/
│       ├── document_parser.py   # PDF/image text extraction, chunking, embedding
│       └── rag_service.py       # Vector search, context building, document analysis
├── scripts/
│   ├── ingest_laws.py          # Law PDF ingestion pipeline
│   ├── _download_pdfs.py       # PDF downloader from India Code
│   ├── _find_handles.py        # Handle discovery tool
│   └── ...
├── data/laws/                  # Bare act PDFs (22 files, gitignored)
├── alembic/                    # Migrations (0001-0003)
└── requirements.txt
```

## EAS Secrets Required

When deploying the backend alongside EAS builds, set these as EAS secrets:

| Secret | Description |
|--------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_CLIENT_EMAIL` | Firebase service account email |
| `FIREBASE_PRIVATE_KEY` | Firebase service account private key |
| `FIREBASE_STORAGE_BUCKET` | Firebase Storage bucket name |

## License

Private — internal use.
