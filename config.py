import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "development")
SECRET_NAME = f"aurora-analytics/{APP_ENV}"


def load() -> None:
    if APP_ENV != "production":
        logger.info("Environment: %s - loading config from environment variables", APP_ENV)
        return

    logger.info("Environment: %s - fetching config from Secrets Manager (%s)", APP_ENV, SECRET_NAME)

    region = os.getenv("AWS_REGION", "us-east-1")
    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
    except ClientError as e:
        raise RuntimeError(f"Could not fetch secret '{SECRET_NAME}': {e}") from e

    values: dict = json.loads(response["SecretString"])
    for key, value in values.items():
        os.environ.setdefault(key, str(value))

    logger.info("Config loaded from Secrets Manager - keys: %s", list(values.keys()))
