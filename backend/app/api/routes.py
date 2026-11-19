from fastapi import APIRouter, Header, HTTPException, status
from app.config import get_settings
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, StatusResponse, SourceInfo, Source
from app.rag.store import KnowledgeStore
from app.scrapers.darglobal import DarGlobalScraper
from app.scrapers.wasalt import WasaltScraper
from app.services.openrouter import generate_answer, OpenRouterError
from app.utils.text import deduplicate_documents


router = APIRouter()
settings = get_settings()
store = KnowledgeStore(settings.data_dir, settings.embedding_model)
GREETING_MESSAGES = {
    "hi", "hello", "hey", "hiya", "howdy", "good morning", "good afternoon",
    "good evening", "namaste", "salaam", "assalamu alaikum",
}


def indexed_websites(documents: list[dict]) -> list[str]:
    return sorted({str(document.get("website", "Unknown")) for document in documents})


def is_greeting(message: str) -> bool:
    normalized = message.casefold().strip().strip("!.,? ")
    return normalized in GREETING_MESSAGES


def verify_admin(x_admin_token: str | None) -> None:
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required")


@router.get("/health", response_model=HealthResponse)
def health():
    documents = store.load_documents()
    return {"status": "ok", "knowledge_ready": bool(documents)}


@router.get("/api/status", response_model=StatusResponse)
def api_status():
    documents = store.load_documents()
    return {
        "backend": "ok",
        "knowledge_base": "ready" if documents else "empty",
        "ai_model_configured": bool(settings.openrouter_api_key),
        "document_count": len(documents),
        "source_websites": indexed_websites(documents),
    }


@router.get("/api/sources", response_model=list[SourceInfo])
def sources():
    documents = store.load_documents()
    grouped: dict[str, dict] = {}
    for document in documents:
        name = document.get("website", "Unknown")
        url = document.get("url", "")
        if name not in grouped:
            grouped[name] = {"name": name, "url": url, "document_count": 0}
        grouped[name]["document_count"] += 1
    return list(grouped.values())


@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if is_greeting(request.message):
        websites = indexed_websites(store.load_documents())
        if websites:
            answer = f"Hi! I can answer questions using indexed public information from {', '.join(websites)}."
            if not any("darglobal" in name.casefold().replace(" ", "") for name in websites):
                answer += " DarGlobal project information is not currently indexed, so I cannot verify its latest projects yet."
            answer += " Ask me about a listed property's location, price, size, or features."
        else:
            answer = "Hi! The knowledge base is empty at the moment, so I cannot verify property details yet."
        return ChatResponse(answer=answer, fallback=True)

    retrieved = store.search(request.message, k=5)
    relevant = [item for item in retrieved if float(item.get("relevance", 0)) >= 0.25]
    normalized_query = request.message.casefold().replace(" ", "").replace("-", "")
    asks_darglobal = "darglobal" in normalized_query
    asks_wasalt = "wasalt" in normalized_query
    if asks_darglobal != asks_wasalt:
        requested_website = "darglobal" if asks_darglobal else "wasalt"
        relevant = [
            item for item in relevant
            if requested_website in str(item.get("website", "")).casefold().replace(" ", "")
        ]
    if not relevant:
        documents = store.load_documents()
        websites = indexed_websites(documents)
        if asks_darglobal and not any("darglobal" in name.casefold().replace(" ", "") for name in websites):
            answer = (
                "I don't have verified DarGlobal pages in the indexed sources. The public DarGlobal site "
                "was not crawlable during the last scrape, so I can't confirm its latest projects without "
                "a source. The current knowledge base includes: "
                f"{', '.join(websites) if websites else 'no sources yet'}."
            )
        elif not documents:
            answer = "The knowledge base is empty, so I don't have verified public property information to answer this yet."
        else:
            answer = (
                "I couldn't find that detail in the currently indexed public pages. "
                f"Indexed sources: {', '.join(websites)}. Try asking about a specific listed property's location, price, size, or features."
            )
        return ChatResponse(
            answer=answer,
            sources=[],
            fallback=True,
        )
    try:
        answer, model = await generate_answer(
            settings.openrouter_api_key,
            settings.model_list,
            settings.openrouter_base_url,
            settings.openrouter_timeout,
            request.message,
            request.history,
            relevant,
        )
    except OpenRouterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    sources = [
        Source(
            title=item.get("title", "Untitled"),
            url=item.get("url", ""),
            website=item.get("website", "Unknown"),
            relevance=float(item.get("relevance", 0)),
            excerpt=item.get("excerpt", ""),
        )
        for item in relevant
        if item.get("url")
    ]
    return ChatResponse(answer=answer, sources=sources, model=model)


@router.post("/api/scrape")
def scrape(limit: int = 30, x_admin_token: str | None = Header(default=None)):
    verify_admin(x_admin_token)
    scrapers = (
        DarGlobalScraper(settings.scrape_rate_limit_seconds),
        WasaltScraper(settings.scrape_rate_limit_seconds),
    )
    collected = []
    for scraper in scrapers:
        try:
            collected.extend(scraper.scrape(limit=limit))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"{scraper.name} scraping failed: {exc}")
    existing = store.load_documents()
    documents = store.save_documents([*existing, *collected])
    return {"documents_added": max(0, len(documents) - len(existing)), "document_count": len(documents)}


@router.post("/api/knowledge/rebuild")
def rebuild(x_admin_token: str | None = Header(default=None)):
    verify_admin(x_admin_token)
    try:
        chunk_count = store.rebuild()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Knowledge rebuild failed: {exc}")
    return {"chunk_count": chunk_count}
