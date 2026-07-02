# Pocket Lawyer API

FastAPI backend for Pocket Lawyer — an AI-powered legal research and document analysis platform. Provides RAG-based retrieval over Indian bare acts and user-uploaded documents using OpenAI embeddings + GPT-4o-mini, with Firebase Authentication.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Expo Client  │────▶│  FastAPI (uvicorn)│────▶│  PostgreSQL 16   │
│  (React Native)│    │  localhost:8000   │    │  + pgvector       │
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

- **Bare Act Ingestion** — Extract sections from Indian law PDFs, generate embeddings, store in pgvector
- **Document Upload** — Upload PDFs, extract text, chunk, embed, and store for RAG
- **AI Legal Q&A** — Ask questions about documents or search legislation; answers grounded in retrieved chunks
- **Firebase Auth** — Token-based authentication with Firebase
- **RAG Pipeline** — `text-embedding-3-small` for vectors, `gpt-4o-mini` for answers, cosine-similarity retrieval
- **22 Indian Bare Acts** pre-mapped and ready for ingestion (see [LAWS_INVENTORY.md](../LAWS_INVENTORY.md))

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| ASGI Server | uvicorn 0.34 |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.14 |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | OpenAI GPT-4o-mini |
| Auth | Firebase Admin SDK |
| PDF Parsing | pdfplumber |

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 16 with pgvector extension
- OpenAI API key
- Firebase project (service account credentials)

### 1. Clone & environment

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

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/pocket_lawyer
OPENAI_API_KEY=sk-...
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`.

## Ingesting Bare Acts

```bash
# Ingest all available PDFs
python -m scripts.ingest_laws

# Ingest a specific act
python -m scripts.ingest_laws --act ipc
python -m scripts.ingest_laws --act "indian penal code"
```

PDFs live in `data/laws/`. See [LAWS_INVENTORY.md](../LAWS_INVENTORY.md) for the full list of acts and download status.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/login` | Firebase token | Create/retrieve user |
| `GET` | `/api/v1/auth/me` | Firebase token | Current user profile |
| `POST` | `/api/v1/documents/upload` | Firebase token | Upload PDF (multipart) |
| `GET` | `/api/v1/documents/` | Firebase token | List user's documents |
| `GET` | `/api/v1/documents/{id}` | Firebase token | Get document details |
| `DELETE` | `/api/v1/documents/{id}` | Firebase token | Delete document |
| `POST` | `/api/v1/chat/messages` | Firebase token | Send message & get AI reply |
| `GET` | `/api/v1/chat/messages` | Firebase token | Chat history |
| `GET` | `/api/v1/laws/search?query=` | Firebase token | Search bare acts |
| `GET` | `/health` | No | Health check |

## Project Structure

```
pocket-lawyer-api/
├── app/
│   ├── main.py                 # FastAPI app, CORS, lifespan
│   ├── core/
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # Async engine, session, init_db
│   │   └── security.py         # Firebase token verification
│   ├── models/
│   │   ├── user.py             # User model
│   │   ├── document.py         # Document + DocumentChunk
│   │   ├── law.py              # LawChunk
│   │   └── chat.py             # ChatMessage
│   ├── api/routes/
│   │   ├── auth.py             # Login, me
│   │   ├── documents.py        # Upload, list, get, delete
│   │   ├── chat.py             # Messages, Q&A
│   │   └── laws.py             # Law search
│   └── services/
│       ├── openai_service.py   # Embedding + chat completion
│       ├── rag_service.py      # Vector search (document chunks)
│       └── document_parser.py  # PDF extraction, chunking, embedding
├── scripts/
│   ├── ingest_laws.py          # Law PDF ingestion pipeline
│   ├── _download_pdfs.py       # PDF downloader from India Code
│   ├── _find_handles.py        # Handle discovery tool
│   └── ...
├── data/laws/                  # Downloaded PDFs
├── alembic/                    # Migrations
└── requirements.txt
```

## License

Private — internal use.
