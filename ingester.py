import logging
import os
import time
from datetime import datetime, timedelta, timezone

import config
import logging_handler
from base import BaseIngester, BasePublisher, RateLimitedError
from publishers.kinesis import KinesisPublisher
from sources.newsapi import NewsAPIIngester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the fetch, transform, deduplicate, and publish cycle."""

    def __init__(self, ingester: BaseIngester, publisher: BasePublisher) -> None:
        self.ingester = ingester
        self.publisher = publisher
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
        self.lookback = int(os.getenv("LOOKBACK_SECONDS", str(self.poll_interval)))
        self._seen_ids: set[str] = set()

    def run(self) -> None:
        logger.info(
            "Ingestion service started - stream=%s, query='%s', interval=%ds, lookback=%ds",
            os.getenv("KINESIS_STREAM_NAME"),
            os.getenv("NEWS_QUERY", "all"),
            self.poll_interval,
            self.lookback,
        )

        last_fetch = datetime.now(timezone.utc) - timedelta(seconds=self.lookback)

        while True:
            cycle_start = datetime.now(timezone.utc)
            logger.info("Polling for articles published since %s", last_fetch.isoformat())

            try:
                raw_articles = self.ingester.fetch(since=last_fetch)
            except RateLimitedError as e:
                logger.warning("Rate limit exhausted. Backing off for %ds before next poll.", e.retry_after)
                time.sleep(e.retry_after)
                continue

            new_articles: list[dict] = []
            for raw in raw_articles:
                article = self.ingester.transform(raw)
                if article is None:
                    continue
                if article["article_id"] in self._seen_ids:
                    continue
                self._seen_ids.add(article["article_id"])
                new_articles.append(article)

            if new_articles:
                written = self.publisher.publish(new_articles)
                logger.info(
                    "Cycle complete: %d new article(s), %d written to stream",
                    len(new_articles),
                    written,
                )
            else:
                logger.info("Cycle complete: no new articles")

            if len(self._seen_ids) > 2000:
                self._seen_ids.clear()
                logger.debug("Cleared seen_ids cache")

            last_fetch = cycle_start
            elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            sleep_for = max(0.0, self.poll_interval - elapsed)
            logger.info("Next poll in %.1fs", sleep_for)
            time.sleep(sleep_for)


if __name__ == "__main__":
    config.load()
    logging.getLogger().addHandler(logging_handler.SQSLogHandler())

    service = IngestionService(
        ingester=NewsAPIIngester(),
        publisher=KinesisPublisher(),
    )
    service.run()
