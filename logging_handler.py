import json
import logging
import os
from datetime import datetime, timezone

import boto3

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "sqs",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("KINESIS_ENDPOINT_URL"),
        )
    return _client


class SQSLogHandler(logging.Handler):
    """Sends WARNING and above log records to an SQS queue."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.queue_url = os.getenv("SQS_LOGS_URL")

    def emit(self, record: logging.LogRecord) -> None:
        if not self.queue_url:
            return
        try:
            _get_client().send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps({
                    "level": record.levelname,
                    "logger": record.name,
                    "message": self.format(record),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, ensure_ascii=False),
            )
        except Exception:
            pass
