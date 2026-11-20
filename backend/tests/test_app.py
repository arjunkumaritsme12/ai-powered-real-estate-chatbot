import json
import sys
import types
from fastapi.testclient import TestClient
from app.main import app
from app.utils.text import clean_html, deduplicate_documents
from app.rag.chunker import chunk_documents
from app.api import routes
from app.scrapers.base import BaseScraper
from app.rag.store import KnowledgeStore


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_greeting(monkeypatch):
    def unexpected_search(*args, **kwargs):
        raise AssertionError("greetings should not run retrieval")

    monkeypatch.setattr(routes.store, "load_documents", lambda: [{"website": "Wasalt"}])
    monkeypatch.setattr(routes.store, "search", unexpected_search)
    response = client.post("/api/chat", json={"message": "hello", "history": []})
    assert response.status_code == 200
    assert "Hi!" in response.json()["answer"]
    assert "Wasalt" in response.json()["answer"]
    assert response.json()["fallback"] is True


def test_darglobal_query_does_not_use_wasalt_documents(monkeypatch):
    monkeypatch.setattr(routes.store, "load_documents", lambda: [{"website": "Wasalt"}])
    monkeypatch.setattr(routes.store, "search", lambda *args, **kwargs: [{
        "website": "Wasalt",
        "relevance": 0.9,
        "title": "Public listing",
        "url": "https://wasalt.sa/property/1",
        "text": "Public listing details",
    }])
    response = client.post(
        "/api/chat",
        json={"message": "What are the latest DarGlobal projects?", "history": []},
    )
    assert response.status_code == 200
    assert "DarGlobal" in response.json()["answer"]
    assert "Wasalt" in response.json()["answer"]
    assert response.json()["sources"] == []


def test_chat_validation():
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_scraper_extraction():
    html = "<html><head><title>Test Project</title></head><body><nav>Menu</nav><h1>Coastal Residence</h1><p>Three bedroom residences.</p></body></html>"
    text = clean_html(html)
    assert "Coastal Residence" in text
    assert "Menu" not in text


def test_scraper_uses_allowed_robots_rules(monkeypatch):
    class Response:
        text = "User-agent: *\nAllow: /\nDisallow: /search\nSitemap: https://example.com/sitemap.xml"

        def raise_for_status(self):
            pass

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout):
            return Response()

    monkeypatch.setattr("app.scrapers.base.requests.Session", Session)
    scraper = BaseScraper()
    assert scraper.can_fetch("https://example.com/listing/1")
    assert not scraper.can_fetch("https://example.com/search")
    assert scraper.sitemap_urls == ["https://example.com/sitemap.xml"]


def test_duplicate_removal():
    docs = [
        {"url": "https://example.com/a", "text": "The same property description"},
        {"url": "https://example.com/b", "text": "The same property description"},
        {"url": "https://example.com/c", "text": "A different property description"},
    ]
    assert len(deduplicate_documents(docs)) == 2


def test_chunking():
    chunks = chunk_documents([{"text": "a " * 1200, "title": "Test", "url": "https://example.com"}])
    assert len(chunks) >= 2
    assert all(chunk.metadata["title"] == "Test" for chunk in chunks)


def test_knowledge_index_load_is_cached(tmp_path, monkeypatch):
    class FakeIndex:
        ntotal = 1

        def search(self, embeddings, k):
            import numpy as np
            return np.array([[0.9]], dtype="float32"), np.array([[0]], dtype="int64")

    class FakeSentenceTransformer:
        constructions = 0

        def __init__(self, model_name):
            type(self).constructions += 1

        def encode(self, texts, normalize_embeddings):
            import numpy as np
            return np.array([[1.0, 0.0]], dtype="float32")

    fake_faiss = types.SimpleNamespace(read_index=lambda path: FakeIndex())
    fake_transformers = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "faiss", fake_faiss)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_transformers)

    store = KnowledgeStore(str(tmp_path))
    store.index_path.touch()
    store.metadata_path.write_text(json.dumps([{
        "text": "A test property",
        "metadata": {"title": "Test", "url": "https://example.com"},
    }]), encoding="utf-8")

    assert store.search("first query")
    assert store.search("second query")
    assert FakeSentenceTransformer.constructions == 1


def test_saving_updated_documents_invalidates_stale_index(tmp_path):
    store = KnowledgeStore(str(tmp_path))
    store.documents_path.write_text("[]", encoding="utf-8")
    store.index_path.write_bytes(b"old index")
    store.metadata_path.write_text("[]", encoding="utf-8")

    store.save_documents([{"title": "New", "url": "https://example.com", "text": "New property"}])

    assert not store.index_path.exists()
    assert not store.metadata_path.exists()
    assert store._index_loaded is False


def test_no_relevant_document_fallback(monkeypatch):
    monkeypatch.setattr(routes.store, "search", lambda *args, **kwargs: [])
    response = client.post("/api/chat", json={"message": "Tell me about Riyadh properties"})
    assert response.status_code == 200
    assert response.json()["fallback"] is True


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(routes.settings, "openrouter_api_key", "")
    monkeypatch.setattr(routes.store, "search", lambda *args, **kwargs: [{
        "title": "Public source",
        "text": "A public project description",
        "url": "https://example.com/project",
        "website": "DarGlobal",
        "relevance": 0.8,
        "excerpt": "A public project description",
    }])
    response = client.post("/api/chat", json={"message": "Describe this project"})
    assert response.status_code == 502
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_openrouter_error(monkeypatch):
    async def fail(*args, **kwargs):
        raise routes.OpenRouterError("OpenRouter unavailable")

    monkeypatch.setattr(routes, "generate_answer", fail)
    monkeypatch.setattr(routes.store, "search", lambda *args, **kwargs: [{
        "title": "Public source",
        "text": "A public project description",
        "url": "https://example.com/project",
        "website": "DarGlobal",
        "relevance": 0.8,
        "excerpt": "A public project description",
    }])
    response = client.post("/api/chat", json={"message": "Describe this project"})
    assert response.status_code == 502
    assert "OpenRouter unavailable" in response.json()["detail"]


def test_source_citation_shape(monkeypatch):
    async def success(*args, **kwargs):
        return "This answer cites the public source.", "test-model"

    monkeypatch.setattr(routes, "generate_answer", success)
    monkeypatch.setattr(routes.store, "search", lambda *args, **kwargs: [{
        "title": "Public source",
        "text": "A public project description",
        "url": "https://example.com/project",
        "website": "DarGlobal",
        "relevance": 0.8,
        "excerpt": "A public project description",
    }])
    response = client.post("/api/chat", json={"message": "Describe this project"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["url"] == "https://example.com/project"
