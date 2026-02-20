import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from sources.newsapi import NewsAPIIngester

VALID_RAW = {
    "source": {"name": "BBC News"},
    "title": "Test Article",
    "url": "https://example.com/article",
    "author": "Jane Smith",
    "content": "Some content...",
    "publishedAt": "2026-02-20T10:00:00Z",
}

SINCE = datetime(2026, 2, 20, tzinfo=timezone.utc)


class TestTransform:
    def setup_method(self):
        self.ingester = NewsAPIIngester()

    def test_valid_article_returns_all_fields(self):
        result = self.ingester.transform(VALID_RAW)
        assert result is not None
        assert result["title"] == "Test Article"
        assert result["url"] == "https://example.com/article"
        assert result["source_name"] == "BBC News"
        assert result["author"] == "Jane Smith"
        assert result["content"] == "Some content..."
        assert result["published_at"] == "2026-02-20T10:00:00Z"
        assert "article_id" in result
        assert "ingested_at" in result

    def test_article_id_is_uuid5_derived_from_url(self):
        result = self.ingester.transform(VALID_RAW)
        expected = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.com/article"))
        assert result["article_id"] == expected

    def test_same_url_always_produces_same_article_id(self):
        result1 = self.ingester.transform(VALID_RAW)
        result2 = self.ingester.transform(VALID_RAW)
        assert result1["article_id"] == result2["article_id"]

    def test_missing_url_returns_none(self):
        assert self.ingester.transform({**VALID_RAW, "url": None}) is None

    def test_empty_url_returns_none(self):
        assert self.ingester.transform({**VALID_RAW, "url": ""}) is None

    def test_missing_title_returns_none(self):
        assert self.ingester.transform({**VALID_RAW, "title": None}) is None

def test_missing_author_stored_as_none(self):
        result = self.ingester.transform({**VALID_RAW, "author": None})
        assert result["author"] is None

    def test_missing_content_stored_as_none(self):
        result = self.ingester.transform({**VALID_RAW, "content": None})
        assert result["content"] is None

    def test_missing_source_defaults_to_unknown(self):
        result = self.ingester.transform({**VALID_RAW, "source": None})
        assert result["source_name"] == "Unknown"


class TestFetch:
    def setup_method(self):
        self.ingester = NewsAPIIngester()

    @patch("sources.newsapi.requests.get")
    def test_fetch_returns_articles_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": [VALID_RAW]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        articles = self.ingester.fetch(SINCE)

        assert len(articles) == 1
        assert articles[0]["title"] == "Test Article"

    @patch("sources.newsapi.dlq.send")
    @patch("sources.newsapi.time.sleep")
    @patch("sources.newsapi.requests.get")
    def test_fetch_retries_on_network_error(self, mock_get, mock_sleep, mock_dlq):
        mock_get.side_effect = requests.RequestException("connection error")

        articles = self.ingester.fetch(SINCE)

        assert articles == []
        assert mock_get.call_count == NewsAPIIngester.MAX_RETRIES
        assert mock_sleep.call_count == NewsAPIIngester.MAX_RETRIES - 1

    @patch("sources.newsapi.dlq.send")
    @patch("sources.newsapi.time.sleep")
    @patch("sources.newsapi.requests.get")
    def test_fetch_sends_to_dlq_after_max_retries(self, mock_get, mock_sleep, mock_dlq):
        mock_get.side_effect = requests.RequestException("connection error")

        self.ingester.fetch(SINCE)

        mock_dlq.assert_called_once()
        assert mock_dlq.call_args[0][0]["source"] == "newsapi"

    @patch("sources.newsapi.dlq.send")
    @patch("sources.newsapi.requests.get")
    def test_fetch_sends_to_dlq_on_api_error_status(self, mock_get, mock_dlq):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "message": "apiKeyInvalid"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.ingester.fetch(SINCE)

        mock_dlq.assert_called_once()
        assert mock_dlq.call_args[0][0]["error"] == "apiKeyInvalid"

    @patch("sources.newsapi.requests.get")
    def test_fetch_stops_early_when_page_is_not_full(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": [VALID_RAW]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.ingester.fetch(SINCE)

        assert mock_get.call_count == 1
