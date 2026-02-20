import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "development")


def _load_from_secrets_manager() -> None:
    secret_name = f"aurora-analytics/{APP_ENV}"
    region = os.getenv("AWS_REGION", "us-east-1")

    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response["SecretString"])
    except ClientError as exc:
        logger.error("Failed to fetch secrets from AWS Secrets Manager: %s", exc)
        raise

    for key, value in secrets.items():
        os.environ.setdefault(key, str(value))

    logger.info("Secrets loaded from AWS Secrets Manager (%s)", secret_name)


def load() -> None:
    if APP_ENV == "production":
        logger.info("Environment: production — loading secrets from AWS Secrets Manager")
        _load_from_secrets_manager()
    else:
        logger.info("Environment: %s — loading config from environment variables", APP_ENV)
