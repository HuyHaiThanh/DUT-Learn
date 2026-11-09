import logging
from uuid import UUID

logger = logging.getLogger(__name__)


def enqueue_ingest(version_id: UUID) -> None:
    """T09 replaces this logging-only integration point with worker scheduling."""
    logger.info("Ingest requested for material version %s", version_id)
