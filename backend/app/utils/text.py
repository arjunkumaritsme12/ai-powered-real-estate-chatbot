import re
from bs4 import BeautifulSoup


def clean_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def deduplicate_documents(documents: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_signatures: set[str] = set()
    result = []
    for document in documents:
        url = (document.get("url") or "").strip()
        text = clean_html(document.get("text") or "")
        signature = re.sub(r"\W+", "", text.lower())[:1000]
        if not text or (url and url in seen_urls) or (signature and signature in seen_signatures):
            continue
        if url:
            seen_urls.add(url)
        if signature:
            seen_signatures.add(signature)
        document["text"] = text
        result.append(document)
    return result
