import hashlib
import json
import logging

import diskcache
from curl_cffi import requests
from lxml import html

from my_toolbox.scraper.agents import generate_random_user_agent
from my_toolbox.scraper.exceptions import ScraperError
from my_toolbox.scraper.rate_limit import RateLimiter

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class CachedScraper:
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        cache_dir=".scraper_cache",
        cache_expiry=None,
        headers=None,
        rate_limiter=None,
    ):
        self.headers = headers if headers is not None else DEFAULT_HEADERS.copy()
        self.headers["User-Agent"] = generate_random_user_agent()
        self.session = requests.Session(impersonate="chrome120")
        self.cache = diskcache.Cache(cache_dir)
        self.cache_expiry = cache_expiry

        self.rate_limiter = (
            rate_limiter if rate_limiter else RateLimiter(mode="flat", flat_delay=1.5)
        )

    def _generate_cache_key(self, url, method="GET", params=None):
        key_base = f"{method}:{url}:{params}"
        return hashlib.md5(key_base.encode("utf-8")).hexdigest()

    def _fetch(self, url):
        """Internal method that handles caching, rate limiting, and networking. Always returns raw bytes."""

        cache_key = self._generate_cache_key(url)

        cached_content = self.cache.get(cache_key)
        if cached_content is not None:
            return cached_content

        self.rate_limiter.enforce()

        self.logger.info(f"[NETWORK FETCH] {url}")
        try:
            response = self.session.get(url, headers=self.headers, timeout=10)
            self.cache.set(cache_key, response.content, expire=self.cache_expiry)
            return response.content

        except ScraperError:
            raise
        except Exception as e:
            raise ScraperError(f"Network failure: {e}", url=url)

    def fetch(self, url):
        """Use this when scraping standard HTML websites."""
        raw_bytes = self._fetch(url)

        return html.fromstring(raw_bytes)

    def fetch_json(self, url):
        """Use this when scraping APIs or hidden JSON endpoints."""
        raw_bytes = self._fetch(url)

        # Explicitly check that we got bytes/str before calling json.loads
        if not isinstance(raw_bytes, (bytes, str)):
            raise ScraperError(
                f"Expected bytes or str from cache/network, got {type(raw_bytes)}"
            )

        return json.loads(raw_bytes)
