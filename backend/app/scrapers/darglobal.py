from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils.text import clean_html


class DarGlobalScraper(BaseScraper):
    name = "DarGlobal"
    base_url = "https://www.darglobal.co.uk/"

    def scrape(self, limit: int = 40) -> list[dict]:
        documents = []
        response = self.get(self.base_url)
        if response is None:
            return documents
        links = self.discover_links(response.text, self.base_url)
        relevant = [link for link in links if any(word in link.lower() for word in (
            "project", "develop", "destination", "properties", "property", "residence", "dubai", "london"
        ))][:limit]
        for url in [self.base_url, *relevant]:
            page = self.get(url)
            if page is None:
                continue
            soup = BeautifulSoup(page.text, "html.parser")
            title = (soup.title.get_text(" ", strip=True) if soup.title else "DarGlobal")
            text = clean_html(str(soup))
            if len(text) < 120:
                continue
            documents.append({
                "title": title,
                "text": text,
                "url": url,
                "website": self.name,
                "developer": "DarGlobal",
                "metadata": {"source": "public_web", "scraper": "darglobal"},
            })
        return documents
