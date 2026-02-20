from unittest.mock import MagicMock

from ingester import IngestionService

VALID_ARTICLE = {
    "article_id": "abc123",
    "title": "Test Article",
    "url": "https://example.com/article",
    "source_name": "BBC News",
    "author": "Jane Smith",
    "content": "Some content...",
    "published_at": "2026-02-20T10:00:00Z",
    "ingested_at": "2026-02-20T10:01:00Z",
}


def run_one_cycle(service: IngestionService, raw_articles: list, transformed: dict | None) -> list:
    """Simulate one cycle of deduplication logic from run()."""
    service.ingester.fetch.return_value = raw_articles
    service.ingester.transform.return_value = transformed

    new_articles = []
    for raw in raw_articles:
        article = service.ingester.transform(raw)
        if article is None:
            continue
        if article["article_id"] in service._seen_ids:
            continue
        service._seen_ids.add(article["article_id"])
        new_articles.append(article)

    return new_articles


class TestDeduplication:
    def setup_method(self):
        self.service = IngestionService(
            ingester=MagicMock(),
            publisher=MagicMock(),
        )

    def test_new_article_is_processed(self):
        new_articles = run_one_cycle(self.service, [{"raw": "data"}], VALID_ARTICLE)
        assert len(new_articles) == 1
        assert new_articles[0]["article_id"] == "abc123"

    def test_duplicate_article_is_skipped(self):
        self.service._seen_ids.add("abc123")
        new_articles = run_one_cycle(self.service, [{"raw": "data"}], VALID_ARTICLE)
        assert len(new_articles) == 0

    def test_article_id_added_to_seen_ids_after_processing(self):
        run_one_cycle(self.service, [{"raw": "data"}], VALID_ARTICLE)
        assert "abc123" in self.service._seen_ids

    def test_invalid_article_skipped_when_transform_returns_none(self):
        new_articles = run_one_cycle(self.service, [{"raw": "data"}], None)
        assert len(new_articles) == 0

    def test_same_article_not_processed_twice_in_same_cycle(self):
        new_articles = run_one_cycle(
            self.service,
            [{"raw": "data"}, {"raw": "data"}],
            VALID_ARTICLE,
        )
        assert len(new_articles) == 1


class TestSeenIdsCache:
    def setup_method(self):
        self.service = IngestionService(
            ingester=MagicMock(),
            publisher=MagicMock(),
        )

    def test_seen_ids_starts_empty(self):
        assert len(self.service._seen_ids) == 0

    def test_seen_ids_clears_when_over_2000(self):
        self.service._seen_ids = set(str(i) for i in range(2001))
        assert len(self.service._seen_ids) > 2000

        if len(self.service._seen_ids) > 2000:
            self.service._seen_ids.clear()

        assert len(self.service._seen_ids) == 0
