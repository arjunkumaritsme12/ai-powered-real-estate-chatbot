from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    metadata: dict


def chunk_documents(documents: list[dict], chunk_size: int = 900, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        text = document.get("text", "").strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + chunk_size - 180, end)
                if boundary > start:
                    end = boundary
            chunks.append(Chunk(text[start:end].strip(), dict(document)))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
