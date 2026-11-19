import argparse
import json
from app.config import get_settings
from app.rag.store import KnowledgeStore
from app.scrapers.darglobal import DarGlobalScraper
from app.scrapers.wasalt import WasaltScraper
from app.utils.text import deduplicate_documents


def main():
    parser = argparse.ArgumentParser(description="Refresh PropertyIQ public web sources")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    store = KnowledgeStore(settings.data_dir, settings.embedding_model)
    documents = []
    for scraper in (DarGlobalScraper(settings.scrape_rate_limit_seconds),
                    WasaltScraper(settings.scrape_rate_limit_seconds)):
        try:
            found = scraper.scrape(limit=args.limit)
            print(f"{scraper.name}: scraped {len(found)} public documents")
            documents.extend(found)
        except Exception as exc:
            print(f"{scraper.name}: scrape failed: {exc}")
    documents = deduplicate_documents([*store.load_documents(), *documents])
    store.save_documents(documents)
    print(f"Knowledge base: {len(documents)} documents")
    if args.rebuild:
        print(f"Rebuilt: {store.rebuild()} chunks")


if __name__ == "__main__":
    main()
