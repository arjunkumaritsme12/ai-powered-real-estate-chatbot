import json
import logging
import threading
from pathlib import Path
from app.rag.chunker import Chunk, chunk_documents
from app.utils.text import deduplicate_documents


logger = logging.getLogger(__name__)


class KnowledgeStore:
    def __init__(self, data_dir: str, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_path = self.data_dir / "scraped_documents.json"
        self.index_path = self.data_dir / "faiss.index"
        self.metadata_path = self.data_dir / "chunks.json"
        self.embedding_model_name = embedding_model
        self.model = None
        self.index = None
        self.chunks: list[Chunk] = []
        self._index_loaded = False
        self._load_lock = threading.RLock()

    def load_documents(self) -> list[dict]:
        if not self.documents_path.exists():
            return []
        with self.documents_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_documents(self, documents: list[dict]) -> list[dict]:
        documents = deduplicate_documents(documents)
        if self.documents_path.exists() and self.load_documents() == documents:
            return documents
        with self.documents_path.open("w", encoding="utf-8") as handle:
            json.dump(documents, handle, ensure_ascii=False, indent=2)
        with self._load_lock:
            self.index = None
            self.chunks = []
            self._index_loaded = False
            self.index_path.unlink(missing_ok=True)
            self.metadata_path.unlink(missing_ok=True)
        return documents

    def rebuild(self) -> int:
        try:
            from sentence_transformers import SentenceTransformer
            import faiss
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Vector dependencies are not installed") from exc

        documents = self.load_documents()
        raw_chunks = chunk_documents(documents)
        if not raw_chunks:
            with self._load_lock:
                self.chunks = []
                self.index = None
                self._index_loaded = True
                self.index_path.unlink(missing_ok=True)
                self.metadata_path.unlink(missing_ok=True)
            return 0
        with self._load_lock:
            model = self._get_model(SentenceTransformer)
            embeddings = model.encode([chunk.text for chunk in raw_chunks], normalize_embeddings=True)
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatIP(dimension)
            index.add(np.asarray(embeddings, dtype="float32"))
            faiss.write_index(index, str(self.index_path))
            with self.metadata_path.open("w", encoding="utf-8") as handle:
                json.dump([{"text": c.text, "metadata": c.metadata} for c in raw_chunks], handle, ensure_ascii=False, indent=2)
            self.index = index
            self.chunks = raw_chunks
            self._index_loaded = True
        return len(raw_chunks)

    def _get_model(self, model_class):
        if self.model is None:
            self.model = model_class(self.embedding_model_name)
        return self.model

    def load_index(self) -> bool:
        with self._load_lock:
            if self._index_loaded:
                return self.index is not None
            self._index_loaded = True
            if not self.index_path.exists() or not self.metadata_path.exists():
                logger.warning("FAISS index or chunk metadata is missing in %s", self.data_dir)
                return False
            try:
                import faiss
                from sentence_transformers import SentenceTransformer
                index = faiss.read_index(str(self.index_path))
                with self.metadata_path.open("r", encoding="utf-8") as handle:
                    rows = json.load(handle)
                model = self._get_model(SentenceTransformer)
                chunks = [Chunk(row["text"], row["metadata"]) for row in rows]
                if index.ntotal != len(chunks):
                    raise ValueError(f"FAISS index has {index.ntotal} vectors but metadata has {len(chunks)} chunks")
                self.index = index
                self.chunks = chunks
                return True
            except Exception:
                self.index = None
                self.chunks = []
                self._index_loaded = False
                logger.exception("Could not load FAISS knowledge index from %s", self.data_dir)
                raise

    def search(self, query: str, k: int = 5) -> list[dict]:
        if not self.load_index():
            return []
        import numpy as np
        query_embedding = self.model.encode([query], normalize_embeddings=True)
        scores, indices = self.index.search(np.asarray(query_embedding, dtype="float32"), k)
        results = []
        for score, index in zip(scores[0], indices[0]):
            if index < 0:
                continue
            chunk = self.chunks[int(index)]
            metadata = dict(chunk.metadata)
            metadata["relevance"] = float(score)
            metadata["excerpt"] = chunk.text[:500]
            results.append(metadata)
        return results
