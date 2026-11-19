import logging
import time
import gzip
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup


logger = logging.getLogger("propertyiq.scraper")


class BaseScraper:
    name = ""
    base_url = ""

    def __init__(self, rate_limit_seconds: float = 1.0, timeout: int = 20):
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PropertyIQ/1.0 (public real-estate research bot)"})
        self.last_request = 0.0
        self.robot = RobotFileParser()
        self.robots_loaded = False
        self.sitemap_urls: list[str] = []
        robots_url = urljoin(self.base_url, "/robots.txt")
        self.robot.set_url(robots_url)
        try:
            response = self.session.get(robots_url, timeout=self.timeout)
            response.raise_for_status()
            if "<html" in response.text[:500].lower():
                raise ValueError(f"robots.txt returned HTML instead of crawl rules: {robots_url}")
            lines = response.text.splitlines()
            self.robot.parse(lines)
            self.robot.modified()
            self.sitemap_urls = [
                line.split(":", 1)[1].strip()
                for line in lines
                if line.strip().lower().startswith("sitemap:")
            ]
            self.robots_loaded = True
        except Exception as exc:
            logger.warning("Could not read robots.txt for %s: %s", self.base_url, exc)

    def can_fetch(self, url: str) -> bool:
        if not self.robots_loaded:
            return False
        try:
            user_agent = self.session.headers["User-Agent"]
            matching_entries = [
                entry for entry in self.robot.entries if entry.applies_to(user_agent)
            ]
            if not matching_entries and self.robot.default_entry:
                matching_entries = [self.robot.default_entry]

            parsed_url = urlparse(unquote(url))
            path = urlunparse(("", "", parsed_url.path, parsed_url.params, parsed_url.query, parsed_url.fragment))
            path = quote(path or "/")
            matching_rules = [
                rule
                for entry in matching_entries
                for rule in entry.rulelines
                if rule.applies_to(path)
            ]
            if not matching_rules:
                return True

            specificity = max(len(rule.path.rstrip("*$")) for rule in matching_rules)
            most_specific = [
                rule for rule in matching_rules
                if len(rule.path.rstrip("*$")) == specificity
            ]
            return any(rule.allowance for rule in most_specific)
        except Exception:
            logger.exception("Could not evaluate robots.txt for %s", url)
            return False

    def get(self, url: str) -> requests.Response | None:
        if not self.can_fetch(url):
            logger.warning("Blocked by robots.txt: %s", url)
            return None
        elapsed = time.monotonic() - self.last_request
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=self.timeout)
                self.last_request = time.monotonic()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                logger.warning("Request failed (%s/%s) %s: %s", attempt + 1, 3, url, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return None

    def discover_sitemap_urls(self, limit: int = 30) -> list[str]:
        discovered: list[str] = []
        root_host = urlparse(self.base_url).hostname or ""
        sitemap_files = [
            sitemap for sitemap in self.sitemap_urls
            if urlparse(sitemap).hostname == root_host
            or (urlparse(sitemap).hostname or "").endswith(f".{root_host}")
        ]
        sitemap_files.sort(key=lambda sitemap: (
            0 if "product_sitemap" in sitemap else
            1 if "rental_pdp_sitemap" in sitemap else
            2 if "category_sitemap" in sitemap else
            3 if "rental_srp_sitemap" in sitemap else
            4
        ))
        for sitemap_url in sitemap_files:
            response = self.get(sitemap_url)
            if response is None:
                continue
            content = response.content
            if content.startswith(b"\x1f\x8b"):
                try:
                    content = gzip.decompress(content)
                except OSError as exc:
                    logger.warning("Could not decompress sitemap %s: %s", sitemap_url, exc)
                    continue
            try:
                root = ET.fromstring(content)
            except ET.ParseError as exc:
                logger.warning("Could not parse sitemap %s: %s", sitemap_url, exc)
                continue
            is_index = root.tag.rsplit("}", 1)[-1] == "sitemapindex"
            for location in root.findall(".//{*}loc"):
                candidate = (location.text or "").strip()
                host = urlparse(candidate).hostname or ""
                if is_index or host != root_host:
                    continue
                if not self.can_fetch(candidate):
                    continue
                discovered.append(candidate)
                if len(discovered) >= limit:
                    return list(dict.fromkeys(discovered))
        return list(dict.fromkeys(discovered))

    def discover_links(self, html: str, url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        allowed_host = urlparse(self.base_url).netloc
        links = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            absolute = urljoin(url, href)
            if urlparse(absolute).netloc == allowed_host:
                links.append(absolute.split("#")[0])
        return list(dict.fromkeys(links))
