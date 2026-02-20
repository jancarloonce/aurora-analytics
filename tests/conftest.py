import os
import sys

# Add project root to path so tests can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required env vars before any module is imported
os.environ.setdefault("NEWSAPI_KEY", "test-key")
os.environ.setdefault("KINESIS_STREAM_NAME", "test-stream")
os.environ.setdefault("AWS_REGION", "us-east-1")
