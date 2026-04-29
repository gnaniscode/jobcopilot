"""Abstract base class for job sources."""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from jobcopilot.sources.schemas import Job


class JobSource(ABC):
    """All job source connectors implement this interface."""

    name: str  # subclasses set this — e.g. "greenhouse"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @abstractmethod
    async def fetch_jobs(self, company: str) -> AsyncIterator[Job]:
        """Yield all currently-open jobs for a given company.

        Implementations should:
        - Handle pagination internally
        - Skip postings the source marks as closed/expired
        - Raise httpx.HTTPStatusError on non-recoverable HTTP failures
        """
        ...