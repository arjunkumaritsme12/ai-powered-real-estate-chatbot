from bs4 import BeautifulSoup
from .base import BaseScraper
from ..utils.text import clean_html


class WasaltScraper(BaseScraper):
    name = "Wasalt"
    base_url = "https://wasalt.sa/"

    def scrape(self, limit: int = 40) -> list[dict]:
        documents = []
        response = self.get(self.base_url)
        if response is None:
            return documents
        links = self.discover_links(response.text, self.base_url)
        relevant = [
            link for link in links
            if any(word in link.lower() for word in (
                "propert", "villa", "apartment", "riyadh", "jeddah", "dammam",
                "compound", "listing", "الرياض", "جدة", "مكة", "المدينة"
            ))
            and "/search" not in link.lower()
        ]
        sitemap_links = self.discover_sitemap_urls(limit=max(0, limit - 1))
        page_urls = list(dict.fromkeys([self.base_url, *sitemap_links, *relevant]))[:limit]
        for url in page_urls:
            page = self.get(url)
            if page is None:
                continue
            soup = BeautifulSoup(page.text, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else "Wasalt"
            text = clean_html(str(soup))
            if len(text) < 120:
                continue
            documents.append({
                "title": title,
                "text": text,
                "url": url,
                "website": self.name,
                "metadata": {"source": "public_web", "scraper": "wasalt"},
            })
        return documents
