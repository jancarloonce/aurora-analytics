import json
import os

import boto3

import config

STREAM_NAME = os.getenv("KINESIS_STREAM_NAME", "aurora-news-stream")
REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT_URL = os.getenv("KINESIS_ENDPOINT_URL")

RECORD_LIMIT = 10


def main() -> None:
    config.load()

    client = boto3.client(
        "kinesis",
        region_name=REGION,
        endpoint_url=ENDPOINT_URL,
    )

    shard_response = client.get_shard_iterator(
        StreamName=STREAM_NAME,
        ShardId="shardId-000000000000",
        ShardIteratorType="TRIM_HORIZON",
    )
    iterator = shard_response["ShardIterator"]

    records_response = client.get_records(ShardIterator=iterator, Limit=RECORD_LIMIT)
    records = records_response.get("Records", [])

    if not records:
        print("No records found in stream yet.")
        return

    print(f"\nFound {len(records)} record(s):\n")
    for i, record in enumerate(records, 1):
        article = json.loads(record["Data"])
        print(f"--- Article {i} ---")
        print(json.dumps(article, indent=2))
        print()


if __name__ == "__main__":
    main()
