from abc import ABC, abstractmethod
from datetime import datetime


class RateLimitedError(Exception):
    """Raised when the upstream API rate limit is exhausted after all retries."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s.")


class BaseIngester(ABC):
    """Pulls data from a source and maps it to the canonical article schema."""

    @abstractmethod
    def fetch(self, since: datetime) -> list[dict]:
        """Retrieve raw records from the data source published after since."""

    @abstractmethod
    def transform(self, raw: dict) -> dict | None:
        """Map a single raw record to the canonical article schema.

        Returns None if the record should be discarded.
        """


class BasePublisher(ABC):
    """Pushes processed articles to a destination."""

    @abstractmethod
    def publish(self, articles: list[dict]) -> int:
        """Send articles to the destination.

        Returns the number of successfully delivered records.
        """
