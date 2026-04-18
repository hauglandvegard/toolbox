import hashlib
import json
import logging
from typing import Dict, Optional

import diskcache
from curl_cffi import requests
from curl_cffi.requests.session import RetryStrategy
from lxml import html

from my_toolbox.scraper.agents import generate_random_user_agent
from my_toolbox.scraper.constraints import DEFAULT_HEADERS, DEFAULT_TIMEOUT
from my_toolbox.scraper.exceptions import ScraperError
from my_toolbox.scraper.rate_limit import RateLimiter


class CachedScraper:
    """Web scraper with integrated disk caching, browser impersonation, and rate limiting."""

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        cache_dir=".scraper_cache",
        cache_expiry=None,
        headers=None,
        rate_limiter=None,
    ):
        """Initializes session and cache. Randomizes User-Agent if headers are not provided."""
        if headers is None:
            self.headers = DEFAULT_HEADERS.copy()
            self.headers["User-Agent"] = generate_random_user_agent()
        else:
            self.headers = headers

        strategy = RetryStrategy(
            count=5,
            delay=2,
            backoff="exponential",
            jitter=0.2,  # Adds +/- 20% randomness to timing
        )

        self.session = requests.Session(impersonate="chrome120", retry=strategy)
        self.cache = diskcache.Cache(cache_dir)
        self.status_code = 0
        self.cache_expiry = cache_expiry

        self.rate_limiter = rate_limiter or RateLimiter(mode="flat", flat_delay=1.5)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _generate_cache_key(
        self, url: str, method: str = "GET", params: Optional[Dict] = None
    ) -> str:
        """Generates a stable MD5 hash by sorting parameters."""
        # Ensure params are sorted so order doesn't change the hash
        serialized_params = json.dumps(params, sort_keys=True) if params else ""
        key_base = f"{method.upper()}:{url}:{serialized_params}"
        return hashlib.md5(key_base.encode("utf-8")).hexdigest()

    def _fetch(self, url) -> bytes:
        """Internal method that handles caching, rate limiting, and networking. Always returns raw bytes."""
        cache_key = self._generate_cache_key(url)

        cached_content = self.cache.get(cache_key)
        if cached_content is not None:
            self.logger.info(f"[CACHE] {url}")

            if not isinstance(cached_content, bytes):
                raise ScraperError(
                    f"Expected bytes or str from cache, got {type(cached_content)}"
                )
            return cached_content

        self.rate_limiter.enforce()

        self.logger.info(f"[NETWORK] {url}")
        self.rate_limiter.enforce()

        try:
            response = self.session.get(
                url, headers=self.headers, timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            self.logger.debug(f"[NETWORK] Status code: {response.status_code}")
            self.status_code = response.status_code
            self.cache.set(cache_key, response.content, expire=self.cache_expiry)
            return response.content

        except ScraperError:
            raise
        except Exception as e:
            raise ScraperError(f"Network failure: {e}", url=url)

    def fetch(self, url) -> html.HtmlElement:
        """Use this when scraping standard HTML websites."""
        raw_bytes = self._fetch(url)

        return html.fromstring(raw_bytes)

    def fetch_json(self, url) -> dict:
        """Use this when scraping APIs or hidden JSON endpoints."""
        raw_bytes = self._fetch(url)

        return json.loads(raw_bytes)
