import json
import logging
import os
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

import dlq
from base import BasePublisher

logger = logging.getLogger(__name__)


class KinesisPublisher(BasePublisher):
    """Writes article records to an AWS Kinesis Data Stream."""

    BATCH_LIMIT = 500
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2

    def __init__(self) -> None:
        self.stream_name = os.environ["KINESIS_STREAM_NAME"]
        self.client = boto3.client(
            "kinesis",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("KINESIS_ENDPOINT_URL"),
        )

    def _put_records_with_retry(self, records: list[dict]) -> int:
        pending = records

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.client.put_records(
                    StreamName=self.stream_name,
                    Records=pending,
                )
            except (ClientError, BotoCoreError) as exc:
                logger.error("Kinesis PutRecords failed (attempt %d/%d): %s", attempt, self.MAX_RETRIES, exc)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF * attempt)
                    continue
                logger.error("Dropping entire batch of %d record(s) after %d attempts", len(pending), self.MAX_RETRIES)
                for record in pending:
                    dlq.send({"source": "kinesis", "record": json.loads(record["Data"]), "error": str(exc)})
                return 0

            failed_count = response.get("FailedRecordCount", 0)

            if failed_count == 0:
                return len(pending)

            failed_records = [
                pending[i]
                for i, result in enumerate(response["Records"])
                if result.get("ErrorCode")
            ]

            logger.warning(
                "%d record(s) failed in Kinesis (attempt %d/%d), retrying",
                failed_count, attempt, self.MAX_RETRIES,
            )

            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_BACKOFF * attempt)
                pending = failed_records
            else:
                logger.error("%d record(s) dropped after %d attempts", len(failed_records), self.MAX_RETRIES)
                for record in failed_records:
                    dlq.send({"source": "kinesis", "record": json.loads(record["Data"]), "error": "FailedRecordCount"})
                return len(records) - len(failed_records)

        return 0

    def publish(self, articles: list[dict]) -> int:
        if not articles:
            return 0

        success_total = 0

        for offset in range(0, len(articles), self.BATCH_LIMIT):
            batch = articles[offset: offset + self.BATCH_LIMIT]
            records = [
                {
                    "Data": json.dumps(article, ensure_ascii=False).encode("utf-8"),
                    "PartitionKey": article["article_id"],
                }
                for article in batch
            ]

            success_total += self._put_records_with_retry(records)

        logger.info("%d record(s) successfully written to Kinesis", success_total)
        return success_total
