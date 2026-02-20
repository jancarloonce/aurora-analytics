from unittest.mock import MagicMock, patch

import pytest

from publishers.kinesis import KinesisPublisher

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


class TestPublish:
    def setup_method(self):
        with patch("boto3.client"):
            self.publisher = KinesisPublisher()
        self.publisher.client = MagicMock()

    def test_publish_empty_list_returns_zero(self):
        assert self.publisher.publish([]) == 0
        self.publisher.client.put_records.assert_not_called()

    def test_publish_success_returns_count(self):
        self.publisher.client.put_records.return_value = {
            "FailedRecordCount": 0,
            "Records": [{"SequenceNumber": "1", "ShardId": "shardId-000000000000"}],
        }

        result = self.publisher.publish([VALID_ARTICLE])

        assert result == 1
        self.publisher.client.put_records.assert_called_once()

    def test_publish_uses_article_id_as_partition_key(self):
        self.publisher.client.put_records.return_value = {
            "FailedRecordCount": 0,
            "Records": [{"SequenceNumber": "1", "ShardId": "shardId-000000000000"}],
        }

        self.publisher.publish([VALID_ARTICLE])

        call_args = self.publisher.client.put_records.call_args[1]
        assert call_args["Records"][0]["PartitionKey"] == "abc123"

    @patch("publishers.kinesis.time.sleep")
    def test_publish_retries_failed_records(self, mock_sleep):
        self.publisher.client.put_records.side_effect = [
            {
                "FailedRecordCount": 1,
                "Records": [{"ErrorCode": "ProvisionedThroughputExceededException", "ErrorMessage": "throttled"}],
            },
            {
                "FailedRecordCount": 0,
                "Records": [{"SequenceNumber": "1", "ShardId": "shardId-000000000000"}],
            },
        ]

        self.publisher.publish([VALID_ARTICLE])

        assert self.publisher.client.put_records.call_count == 2

    @patch("publishers.kinesis.dlq.send")
    @patch("publishers.kinesis.time.sleep")
    def test_publish_sends_to_dlq_after_max_retries(self, mock_sleep, mock_dlq):
        self.publisher.client.put_records.return_value = {
            "FailedRecordCount": 1,
            "Records": [{"ErrorCode": "ProvisionedThroughputExceededException", "ErrorMessage": "throttled"}],
        }

        self.publisher.publish([VALID_ARTICLE])

        mock_dlq.assert_called_once()
        assert mock_dlq.call_args[0][0]["source"] == "kinesis"
        assert mock_dlq.call_args[0][0]["record"]["article_id"] == "abc123"

    @patch("publishers.kinesis.dlq.send")
    @patch("publishers.kinesis.time.sleep")
    def test_publish_sends_to_dlq_on_client_error(self, mock_sleep, mock_dlq):
        from botocore.exceptions import ClientError
        self.publisher.client.put_records.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Stream not found"}},
            "PutRecords",
        )

        result = self.publisher.publish([VALID_ARTICLE])

        assert result == 0
        mock_dlq.assert_called_once()
        assert mock_dlq.call_args[0][0]["source"] == "kinesis"
