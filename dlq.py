import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)

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


def send(payload: dict) -> None:
    queue_url = os.getenv("SQS_DLQ_URL")
    if not queue_url:
        return

    try:
        _get_client().send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(
                {**payload, "failed_at": datetime.now(timezone.utc).isoformat()},
                ensure_ascii=False,
            ),
        )
        logger.info("Sent failed record to DLQ (source=%s)", payload.get("source"))
    except Exception as exc:
        logger.error("Could not send to DLQ: %s", exc)
