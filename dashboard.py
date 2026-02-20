import json
import os
import time
from collections import Counter
from datetime import datetime, timezone

import boto3
import pandas as pd
import streamlit as st

import config

config.load()

STREAM_NAME = os.environ["KINESIS_STREAM_NAME"]
REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT_URL = os.getenv("KINESIS_ENDPOINT_URL")
REFRESH_INTERVAL = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "10"))
RECORD_LIMIT = 100


def get_kinesis_client():
    return boto3.client(
        "kinesis",
        region_name=REGION,
        endpoint_url=ENDPOINT_URL,
    )


def fetch_all_records() -> list[dict]:
    client = get_kinesis_client()

    try:
        stream = client.describe_stream_summary(StreamName=STREAM_NAME)
        shard_count = stream["StreamDescriptionSummary"]["OpenShardCount"]
    except Exception as e:
        st.error(f"Could not connect to Kinesis stream '{STREAM_NAME}': {e}")
        return []

    records: list[dict] = []

    for shard_index in range(shard_count):
        shard_id = f"shardId-{shard_index:012d}"
        try:
            iterator_response = client.get_shard_iterator(
                StreamName=STREAM_NAME,
                ShardId=shard_id,
                ShardIteratorType="TRIM_HORIZON",
            )
            iterator = iterator_response["ShardIterator"]

            fetched = 0
            while iterator and fetched < RECORD_LIMIT:
                response = client.get_records(ShardIterator=iterator, Limit=RECORD_LIMIT)
                for rec in response["Records"]:
                    try:
                        records.append(json.loads(rec["Data"].decode("utf-8")))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                fetched += len(response["Records"])
                iterator = response.get("NextShardIterator") if response["Records"] else None

        except Exception as e:
            st.warning(f"Could not read shard {shard_id}: {e}")

    records.sort(key=lambda r: r.get("ingested_at", ""), reverse=True)
    return records


def build_chart_data(records: list[dict]) -> pd.DataFrame | None:
    buckets: Counter = Counter()
    for r in records:
        ingested_at = r.get("ingested_at", "")
        if ingested_at:
            # Truncate to the minute: "YYYY-MM-DDTHH:MM"
            bucket = ingested_at[:16].replace("T", " ")
            buckets[bucket] += 1

    if not buckets:
        return None

    df = pd.DataFrame(
        list(buckets.items()),
        columns=["Time (UTC)", "Articles"],
    ).sort_values("Time (UTC)").set_index("Time (UTC)")
    return df


def render_article(article: dict) -> None:
    with st.container(border=True):
        st.markdown(f"### [{article.get('title', 'Untitled')}]({article.get('url', '#')})")

        col1, col2, col3 = st.columns(3)
        col1.markdown(f"**Source:** {article.get('source_name', 'Unknown')}")
        col2.markdown(f"**Author:** {article.get('author') or 'N/A'}")
        col3.markdown(f"**Published:** {article.get('published_at', 'N/A')}")

        if article.get("content"):
            st.markdown(article["content"])

        st.caption(
            f"Article ID: {article.get('article_id', 'N/A')} | "
            f"Ingested at: {article.get('ingested_at', 'N/A')}"
        )


def render_log_entry(index: int, article: dict) -> None:
    with st.expander(f"Article {index} - {article.get('title', 'Untitled')[:80]}"):
        st.code(json.dumps(article, indent=2), language="json")


def main() -> None:
    st.set_page_config(
        page_title="Aurora Analytics",
        page_icon="aurora",
        layout="wide",
    )

    st.title("Aurora Analytics - Live News Stream")
    st.caption(f"Stream: `{STREAM_NAME}` | Region: `{REGION}` | Auto-refresh every {REFRESH_INTERVAL}s")

    col_refresh, col_count = st.columns([1, 4])
    manual_refresh = col_refresh.button("Refresh now")

    if "last_fetch" not in st.session_state or manual_refresh:
        st.session_state.records = fetch_all_records()
        st.session_state.last_fetch = datetime.now(timezone.utc).isoformat()

    records = st.session_state.records
    col_count.markdown(
        f"**{len(records)} article(s)** in stream - last fetched at `{st.session_state.last_fetch}`"
    )

    # Chart
    st.subheader("Articles Ingested Over Time")
    chart_data = build_chart_data(records)
    if chart_data is not None:
        st.bar_chart(chart_data, y="Articles")
    else:
        st.info("No data to chart yet.")

    st.divider()

    # Tabs
    tab_articles, tab_logs = st.tabs(["Articles", "Logs"])

    with tab_articles:
        if not records:
            st.info("No records found in the stream yet. The ingester may still be starting up.")
        else:
            for article in records:
                render_article(article)

    with tab_logs:
        if not records:
            st.info("No records found in the stream yet.")
        else:
            st.caption(f"Showing {len(records)} record(s) from stream - newest first")
            for i, article in enumerate(records, 1):
                render_log_entry(i, article)

    time.sleep(REFRESH_INTERVAL)
    st.rerun()


if __name__ == "__main__":
    main()
