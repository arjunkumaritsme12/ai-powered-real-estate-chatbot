# PropertyIQ - DarGlobal & Wasalt AI Assistant

PropertyIQ is a grounded real-estate RAG chatbot that answers questions using publicly accessible DarGlobal and Wasalt web content. It never treats missing context as evidence and keeps original source URLs for citation.

## Features

- Public website scraping with robots.txt checks, rate limiting, retries, cleaning and deduplication
- FAISS vector retrieval with Sentence Transformers
- Grounded OpenRouter chat completions with model fallback
- Source citations and relevance scores
- Browser-persisted conversation history with thread switching and deletion
- Responsive React, TypeScript and Tailwind-inspired luxury interface
- Docker Compose deployment and Render configuration
- Health, status, scrape and rebuild APIs

## Architecture

```mermaid
flowchart LR
  U[React UI] -->|Chat request| F[FastAPI]
  F -->|Semantic search| V[(FAISS)]
  F -->|Context| O[OpenRouter]
  S[DarGlobal / Wasalt scrapers] --> J[Structured JSON]
  J --> C[Chunking & embeddings]
  C --> V
  O --> F
  F --> U
```

## Local setup

```powershell
Copy-Item .env.example .env
py -m pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

## Scraping and knowledge rebuild

```powershell
cd backend
python -m app.scrape_cli --limit 30 --rebuild
```

Scraping is limited to publicly accessible pages allowed by robots.txt and is best-effort. If a site blocks requests or changes markup, no fabricated records are added.

Administrative requests:

```powershell
curl.exe -X POST "http://localhost:8000/api/scrape?limit=30" -H "X-Admin-Token: $env:ADMIN_TOKEN"
curl.exe -X POST "http://localhost:8000/api/knowledge/rebuild" -H "X-Admin-Token: $env:ADMIN_TOKEN"
```

## Environment variables

| Variable | Purpose |
|---|---|
| OPENROUTER_API_KEY | Server-side OpenRouter credential |
| OPENROUTER_MODEL | Preferred free model |
| OPENROUTER_FALLBACK_MODELS | Comma-separated model fallbacks |
| OPENROUTER_TIMEOUT | Request timeout in seconds |
| ADMIN_TOKEN | Optional protection for scrape/rebuild endpoints |
| CORS_ORIGINS | Comma-separated allowed frontend origins |
| API_BASE_URL | Optional frontend API base URL, including `/api`; leave empty to use the local reverse proxy |
| DATA_DIR | Scraped JSON and FAISS storage directory |

Never commit `.env` or expose the API key to frontend code.

## API

- `GET /health`
- `GET /api/status` (includes indexed source websites and document count)
- `GET /api/sources`
- `POST /api/chat` with `{ "message": "...", "history": [] }`
- `POST /api/scrape`
- `POST /api/knowledge/rebuild`

## Tests

```powershell
cd backend
py -m pytest -q
cd ../frontend
npm run build
```

## Deployment

1. Push the repository to GitHub.
2. In Render, create a Blueprint from `render.yaml`.
3. Set `OPENROUTER_API_KEY` on the backend service. The Blueprint configures the frontend's runtime API URL, backend CORS origin, and a currently available free model.
4. The bundled Wasalt JSON and FAISS index are included in the backend image. The embedding model is downloaded during image build and loaded with the index during production startup. On Docker deployments with a fresh empty data volume, the entrypoint seeds that volume before starting the API.
5. Add a managed persistent disk or external storage for `/app/data` in production if available. Render's free filesystem is ephemeral; the bundled seed remains in each image, but newly scraped data can be lost when an instance is replaced.
6. If the Render service URLs differ from `propertyiq.onrender.com` and `propertyiq-api.onrender.com`, update `CORS_ORIGINS` and the frontend `API_BASE_URL` environment variable to match the actual service URLs, then redeploy both services.

No live URL should be claimed until the deployed endpoint is tested successfully.

## Limitations

- Public web structures change and scraping can be blocked.
- Free OpenRouter models and quotas vary.
- Availability and prices are not inferred.
- Browser session history is in-memory only.
- Render's free tier may not preserve local vector storage.
