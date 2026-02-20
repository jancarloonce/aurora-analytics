import logging
import os
import time
import uuid
from datetime import datetime, timezone

import requests

import dlq
from base import BaseIngester

logger = logging.getLogger(__name__)


class NewsAPIIngester(BaseIngester):
    """Fetches articles from the NewsAPI Everything endpoint."""

    BASE_URL = "https://newsapi.org/v2/everything"

    PAGE_SIZE = 100
    MAX_PAGES = 1
    MAX_RETRIES = 3
    RETRY_BACKOFF = 5

    def __init__(self) -> None:
        self.api_key = os.environ["NEWSAPI_KEY"]
        self.query = os.getenv("NEWS_QUERY")
        self.language = os.getenv("NEWS_LANGUAGE")

    def _fetch_page(self, params: dict) -> list[dict] | None:
        safe_params = {k: v for k, v in params.items() if k != "apiKey"}

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                logger.warning("NewsAPI request failed (attempt %d/%d): %s", attempt, self.MAX_RETRIES, exc)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF * attempt)
                    continue
                logger.error("NewsAPI request failed after %d attempts. params=%s", self.MAX_RETRIES, safe_params)
                dlq.send({"source": "newsapi", "params": safe_params, "error": str(exc)})
                return None

            if data.get("status") != "ok":
                error_msg = data.get("message", "unknown")
                logger.error("NewsAPI returned an error: %s. params=%s", error_msg, safe_params)
                dlq.send({"source": "newsapi", "params": safe_params, "error": error_msg})
                return None

            return data.get("articles", [])

        return None

    def fetch(self, since: datetime) -> list[dict]:
        articles: list[dict] = []
        from_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        for page in range(1, self.MAX_PAGES + 1):
            params: dict = {
                "pageSize": self.PAGE_SIZE,
                "from": from_str,
                "sortBy": "publishedAt",
                "page": page,
                "apiKey": self.api_key,
            }

            if self.query:
                params["q"] = self.query
            if self.language:
                params["language"] = self.language

            page_articles = self._fetch_page(params)

            if page_articles is None:
                break

            articles.extend(page_articles)
            logger.info("Fetched %d articles from page %d", len(page_articles), page)

            if len(page_articles) < self.PAGE_SIZE:
                break

        return articles

    def transform(self, raw: dict) -> dict | None:
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()

        if not url or not title:
            return None

        return {
            "article_id": str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
            "source_name": ((raw.get("source") or {}).get("name") or "Unknown").strip(),
            "title": title,
            "content": (raw.get("content") or "").strip() or None,
            "url": url,
            "author": (raw.get("author") or "").strip() or None,
            "published_at": raw.get("publishedAt"),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
