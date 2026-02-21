# Aurora Analytics - News Ingest Pipeline

A real-time news ingestion service that polls the [NewsAPI](https://newsapi.org) Everything endpoint and streams structured article records to an **AWS Kinesis Data Stream**.

> **AWS Kinesis is fully implemented.** The service runs locally using LocalStack to emulate Kinesis, and is deployed on an EC2 instance with an IAM role writing directly to a real AWS Kinesis stream. A live deployment is already running on AWS. See [Live Deployment](#live-deployment) to verify it.

---

## Local and AWS Deployment

| | Kinesis | Credentials | How to run |
|---|---|---|---|
| **Local** | LocalStack - emulates AWS Kinesis locally | Dummy values, no AWS account needed | `make dev-up` |
| **AWS** | Real AWS Kinesis Data Stream | IAM role on EC2 - no credentials needed | Deployed on EC2, see [Production Deployment](#production-deployment) |

All commands are available via the `Makefile`. See the [Make Commands](#make-commands) section for the full reference.

---

## Project Structure

```
aurora-analytics/
├── ingester.py          # Entry point and IngestionService orchestrator
├── base.py              # BaseIngester and BasePublisher abstract classes
├── config.py            # Environment-aware config loader
├── dashboard.py         # Streamlit dashboard - live article viewer
├── dlq.py               # Dead letter queue helper - sends failed records to SQS
├── logging_handler.py   # Custom logging handler - sends WARNING+ logs to SQS
├── sources/
│   └── newsapi.py       # NewsAPIIngester implementation
├── publishers/
│   └── kinesis.py       # KinesisPublisher implementation
├── localstack/
│   └── init.sh          # Creates the Kinesis stream inside LocalStack on startup
├── tests/
│   ├── test_newsapi.py      # Tests for NewsAPIIngester
│   ├── test_kinesis.py      # Tests for KinesisPublisher
│   └── test_ingester.py     # Tests for IngestionService deduplication
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A NewsAPI key: available at [newsapi.org](https://newsapi.org/register)

---

## Quick Start (Local)

Local development runs entirely on your machine using LocalStack as a drop-in AWS replacement. No AWS account or real credentials are required.

**1. Clone the repository**

```bash
git clone <repo-url>
cd aurora-analytics
```

**2. Create your environment file**

```bash
cp .env.example .env
```

Open `.env` and set your NewsAPI key:

```
NEWSAPI_KEY=your_key_here
```

All other values are pre-configured for local dev and do not need to be changed.

**3. Start the services**

```bash
make dev-up
```

This will:
- Start LocalStack and automatically create the `news-api-stream` Kinesis stream
- Build and start the ingester, which will begin polling NewsAPI every 60 seconds

**4. Verify records are flowing**

After approximate 60 seconds, open the dashboard in your browser:

```
http://localhost:8501
```

The dashboard auto-refreshes every 10 seconds. Articles appear in the Articles tab and raw JSON records are visible in the Logs tab.

---

## Dashboard

A Streamlit dashboard is included for viewing articles in real time.

**Run it locally (against LocalStack)**

Start the full stack first if it is not already running:

```bash
make dev-up
```

Then in a second terminal:

```bash
make dev-dashboard
```

Open [http://localhost:8501](http://localhost:8501) in your browser. The dashboard auto-refreshes every 10 seconds, pulling the latest records directly from the Kinesis stream.


| Feature | Detail |
|---|---|
| Auto-refresh | Every 10 seconds (configurable via `DASHBOARD_REFRESH_SECONDS`) |
| Manual refresh | "Refresh now" button at the top |
| Record source | Reads from the beginning of the Kinesis stream (`TRIM_HORIZON`) |
| Multi-shard | Reads all shards automatically |

---

## Production Deployment

Production runs on an EC2 instance with an IAM role attached. The IAM role provides AWS credentials automatically - no credentials or config files are passed or stored anywhere. All configuration is pulled from AWS Secrets Manager at startup.

**1. Create the secret in Secrets Manager**

In the AWS Console go to **Secrets Manager > Store a new secret > Other type of secret** and add the following key/value pairs:

| Key | Example value |
|---|---|
| `NEWSAPI_KEY` | `your_newsapi_key` |
| `KINESIS_STREAM_NAME` | `news-api-stream` |
| `SQS_DLQ_URL` | `https://sqs.us-east-1.amazonaws.com/<account-id>/aurora-analytics-dlq` |
| `SQS_LOGS_URL` | `https://sqs.us-east-1.amazonaws.com/<account-id>/aurora-analytics-logs` |
| `NEWS_QUERY` | `technology` |
| `POLL_INTERVAL_SECONDS` | `60` |
| `LOOKBACK_SECONDS` | `86400` |

Name the secret `aurora-analytics/production`.

**2. Launch an EC2 instance**
- Instance type: `t2.micro` (free tier eligible)
- Attach an IAM role with these two policies:
  - `AmazonKinesisFullAccess`
  - `AmazonSQSFullAccess`
  - `SecretsManagerReadWrite` (or a custom policy scoped to `aurora-analytics/production`)
- In the instance's **Security Group**, open two inbound ports:
  - Port `22` (SSH) - to connect to the instance
  - Port `8501` (TCP) - to access the Streamlit dashboard from your browser

**3. Install Docker on the EC2 instance**

```bash
sudo apt update && sudo apt install -y docker.io
sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

Log out and back in for the group change to take effect.

**4. Pull the image**

```bash
docker pull jancarloonce/aurora-analytics
```

**5. Run the ingester**

```bash
docker run -d --restart unless-stopped -e APP_ENV=production -e AWS_REGION=us-east-1 jancarloonce/aurora-analytics
```

**6. Run the dashboard**

```bash
docker run -d --restart unless-stopped -e APP_ENV=production -e AWS_REGION=us-east-1 -p 8501:8501 jancarloonce/aurora-analytics python -m streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
```

Then open `http://<your-ec2-public-ip>:8501` in your browser.

Both containers pick up AWS credentials from the EC2 IAM role and fetch all config from Secrets Manager - no keys, no config files, nothing to pass at runtime.

---

## Updating the Deployment

When a new image is pushed to DockerHub, run the following on the EC2 instance to apply the update:

```bash
docker pull jancarloonce/aurora-analytics
docker stop $(docker ps -q)
docker rm $(docker ps -aq)
docker run -d --restart unless-stopped -e APP_ENV=production -e AWS_REGION=us-east-1 jancarloonce/aurora-analytics
docker run -d --restart unless-stopped -e APP_ENV=production -e AWS_REGION=us-east-1 -p 8501:8501 jancarloonce/aurora-analytics python -m streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
```

---

## Live Deployment

The service is currently running on an AWS EC2 instance (`t2.micro`, `us-east-1`) writing articles to the `news-api-stream` Kinesis stream in real time.

**Dashboard:** [http://54.167.64.160:8501](http://54.167.64.160:8501)

To verify data is also flowing through Kinesis, check the stream via the AWS Console:

**AWS Console > Kinesis > Data Streams > news-api-stream > Data viewer**

---

## Kinesis Record Schema

Each record written to the stream is a UTF-8 encoded JSON object:

```json
{
  "article_id":   "a1b2c3d4-e5f6-...",
  "source_name":  "BBC News",
  "title":        "Tech stocks rally as AI demand grows",
  "content":      "Markets responded positively to earnings...",
  "url":          "https://bbc.co.uk/news/technology-123",
  "author":       "Jane Smith",
  "published_at": "2024-01-15T10:30:00Z",
  "ingested_at":  "2024-01-15T10:31:05.123456+00:00"
}
```


---

## Testing

Tests use `pytest` with `unittest.mock` - no real AWS or network calls are made.

**Install dependencies and run:**

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

Or via Docker (no local Python setup needed):

```bash
docker-compose run --rm ingester python -m pytest tests/ -v
```

**What is tested:**

| File | Coverage |
|---|---|
| `test_newsapi.py` | `transform()` validation, `fetch()` retry logic, DLQ on failure |
| `test_kinesis.py` | `publish()` batching, retry on failed records, DLQ on failure |
| `test_ingester.py` | Deduplication, `seen_ids` cache clearing |

---

## Make Commands

| Command | Description |
|---|---|
| `make test` | Run the test suite |
| `make dev-up` | Build and start local dev with LocalStack |
| `make dev-start` | Start local dev without rebuilding |
| `make dev-down` | Stop all running containers |
| `make dev-dashboard` | Start the Streamlit dashboard against LocalStack |
| `make prod-build` | Build the production Docker image |
| `make prod-push` | Push image to DockerHub |
| `make prod-pull` | Pull image from DockerHub |

---

## Design Notes

- **Deduplication** is handled in-memory using a set of seen `article_id` values. This covers duplicates within a single run. The set is cleared when it exceeds 2000 entries to prevent unbounded memory growth. A container restart will replay articles from the most recent poll window, which is expected in a streaming pipeline where downstream consumers should be idempotent.
- **article_id** is a UUID-5 derived deterministically from the article URL, meaning the same article always produces the same ID regardless of when it was fetched.
- **Validation** rejects any article missing a `url` or `title`. Optional fields (`author`, `content`) are stored as `null` rather than blocking the record.
- **Retry logic** retries failed NewsAPI requests up to 3 times with exponential backoff. Kinesis `PutRecords` failures retry only the failed records, not the entire batch.
- **Dead letter queue** - records that fail after all retries are sent to an SQS queue (`aurora-analytics-dlq`) so nothing is silently lost.
- **Kinesis batching** uses `PutRecords` with batches of up to 500 records, the API maximum, to minimise round trips.
- **LocalStack** is used for local development. Setting `KINESIS_ENDPOINT_URL=http://localstack:4566` redirects all boto3 calls to the local emulator. Removing the variable in production causes boto3 to connect to real AWS with no other code changes.
- **IAM roles** are used in production so no credentials are ever stored or passed to the container. boto3 picks them up automatically from the EC2 instance metadata.
- **Secrets Manager** stores all production config. The app fetches the secret at startup when `APP_ENV=production`, injecting values into the environment before any service initialises.

---

## Extending the Pipeline

The `BaseIngester` / `BasePublisher` separation means new sources and destinations can be added without touching existing code.

**Adding a new data source**

```python
# sources/rss.py
from base import BaseIngester

class RSSIngester(BaseIngester):
    def fetch(self, since):
        ...

    def transform(self, raw):
        ...
```

**Adding a new destination**

```python
# publishers/s3.py
from base import BasePublisher

class S3Publisher(BasePublisher):
    def publish(self, articles):
        ...
```

**Wiring them up**

```python
service = IngestionService(
    ingester=RSSIngester(),
    publisher=S3Publisher(),
)
service.run()
```

---
