import logging
from threading import Event
from uuid import UUID

logger = logging.getLogger(__name__)
wakeup = Event()


def enqueue_ingest(version_id: UUID) -> None:
    """The database is the durable queue; a wakeup can safely be coalesced."""
    logger.info("Ingest requested for material version %s", version_id)
    wakeup.set()
