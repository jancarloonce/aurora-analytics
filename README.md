# Aurora Analytics — News Ingestion Service

A real-time news ingestion service that polls the [NewsAPI](https://newsapi.org) Everything endpoint and streams structured article records to an AWS Kinesis Data Stream.

---

## Project Structure

```
aurora-analytics/
├── ingester.py          # Entry point and IngestionService orchestrator
├── base.py              # BaseIngester and BasePublisher abstract classes
├── config.py            # Environment-aware config loader
├── reader.py            # Reads and prints records from the stream (local dev)
├── sources/
│   └── newsapi.py       # NewsAPIIngester implementation
├── publishers/
│   └── kinesis.py       # KinesisPublisher implementation
├── localstack/
│   └── init.sh          # Creates the Kinesis stream inside LocalStack on startup
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
- For production only: an AWS account with a Kinesis stream and credentials

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
docker-compose up --build
```

This will:
- Start LocalStack and automatically create the `news-api-stream` Kinesis stream
- Build and start the ingester, which will begin polling NewsAPI every 60 seconds

**4. Verify records are flowing**

In a second terminal, run the reader to inspect what has been written to the stream:

```bash
docker-compose run --rm ingester python reader.py
```

Example output:

```
Found 3 record(s):

{
  "article_id": "a1b2c3d4-...",
  "source_name": "BBC News",
  "title": "Tech stocks rally as AI demand grows",
  "content": "Markets responded positively...",
  "url": "https://bbc.co.uk/...",
  "author": "Jane Smith",
  "published_at": "2024-01-15T10:30:00Z",
  "ingested_at": "2024-01-15T10:31:05.123456+00:00"
}
```

---

## Production Deployment

In production the container reads all secrets from AWS Secrets Manager. No sensitive values are passed on the command line or stored in files.

**1. Pull the image from DockerHub**

```bash
docker pull jancarloonce/aurora-analytics
```

Or build it yourself:

```bash
docker build -t jancarloonce/aurora-analytics .
```

**2. Run the container**

```bash
docker run \
  -e APP_ENV=production \
  -e AWS_REGION=us-east-1 \
  jancarloonce/aurora-analytics
```

`AWS_REGION` is the only value passed directly because boto3 needs it to locate Secrets Manager before it can fetch anything else. All other configuration is pulled from `aurora-analytics/production` in Secrets Manager at startup. 

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

## Extending the Pipeline

The `BaseIngester` / `BasePublisher` separation means new sources and destinations can be added without touching existing code.

**Adding a new data source**

```python
# sources/rss.py
from base import BaseIngester

class RSSIngester(BaseIngester):
    def fetch(self, since):
        # fetch from an RSS feed
        ...

    def transform(self, raw):
        # map RSS fields to the Aurora schema
        ...
```

**Adding a new destination**

```python
# publishers/s3.py
from base import BasePublisher

class S3Publisher(BasePublisher):
    def publish(self, articles):
        # write to S3
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
