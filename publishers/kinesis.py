import json
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from base import BasePublisher

logger = logging.getLogger(__name__)


class KinesisPublisher(BasePublisher):
    """Writes article records to an AWS Kinesis Data Stream."""

    BATCH_LIMIT = 500

    def __init__(self) -> None:
        self.stream_name = os.environ["KINESIS_STREAM_NAME"]
        self.client = boto3.client(
            "kinesis",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("KINESIS_ENDPOINT_URL"),
        )

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

            try:
                response = self.client.put_records(
                    StreamName=self.stream_name,
                    Records=records,
                )
            except (ClientError, BotoCoreError) as exc:
                logger.error("Kinesis PutRecords failed: %s", exc)
                continue

            failed = response.get("FailedRecordCount", 0)
            success = len(batch) - failed
            success_total += success

            if failed:
                logger.warning(
                    "%d record(s) failed in batch starting at offset %d",
                    failed,
                    offset,
                )
            else:
                logger.info("%d record(s) written to Kinesis", success)

        return success_total
