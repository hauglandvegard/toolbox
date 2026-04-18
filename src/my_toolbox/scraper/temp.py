import hashlib
import logging

import diskcache
from curl_cffi import requests
from lxml import html

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class ScraperError(Exception):
    """Custom exception raised when the scraper fails to fetch or parse a page."""

    def __init__(self, message, url="", status_code=-1):
        super().__init__(message)

        self.url = url
        self.status_code = status_code


class CachedScraper:
    logger = logging.getLogger(__name__)

    def __init__(
        self, cache_dir=".scraper_cache", cache_expiry=None, headers=DEFAULT_HEADERS
    ):
        self.session = requests.Session(impersonate="chrome120")
        self.cache = diskcache.Cache(cache_dir)
        self.cache_expiry = cache_expiry
        self.headers = headers

    def _generate_cache_key(self, url, method="GET", params=None):
        key_base = f"{method}:{url}:{params}"
        return hashlib.md5(key_base.encode("utf-8")).hexdigest()

    def fetch(self, url):
        cache_key = self._generate_cache_key(url)

        # -------------------
        #  Check cache
        # -------------------

        cached_content = self.cache.get(cache_key)

        if cached_content is not None:
            self.logger.info(f"[CACHE HIT] {url}")
            return html.fromstring(cached_content)

        # ------------------
        # Fetch from web
        # ------------------

        self.logger.info(f"[NETWORK FETCH] {url}")

        try:
            response = self.session.get(url, headers=self.headers, timeout=10)

            if not (200 <= response.status_code < 300):
                self.logger.error(
                    f"Failed to retrieve page. Status code {response.status_code}."
                )
                # Raise an error to force the caller to handle it
                raise ScraperError(f"HTTP Error: {response.status_code} on {url}")

            self.logger.debug(
                f"Successfully retrieved page. Status code {response.status_code}."
            )
            self.cache.set(cache_key, response.content, expire=self.cache_expiry)

            return html.fromstring(response.content)

        except ScraperError:
            raise
        except Exception as e:
            self.logger.error(f"Exception occurred while fetching {url}: {e}")
            raise ScraperError(f"Network failure: {e}")
