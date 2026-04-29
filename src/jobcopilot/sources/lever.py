"""Lever postings API connector.

Docs: https://help.lever.co/hc/en-us/articles/360032977292-What-is-the-public-postings-API
Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
"""
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from html import unescape
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from jobcopilot.sources.base import JobSource 
from jobcopilot.sources.schemas import Job, JobLocation


LEVER_BASE = "https://api.lever.co/v0/postings"


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class LeverSource(JobSource):
    name = "lever"

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _fetch_payload(self, company: str) -> list[dict]:
        url = f"{LEVER_BASE}/{company}"
        response = await self.client.get(url, params={"mode": "json"}, timeout=15.0)
        response.raise_for_status()
        return response.json()

    async def fetch_jobs(self, company: str) -> AsyncIterator[Job]:
        payload = await self._fetch_payload(company)
        for posting in payload:
            yield self._normalize(company, posting)

    @staticmethod
    def _normalize(company: str, raw: dict) -> Job:
        categories = raw.get("categories") or {}
        location_raw = categories.get("location") or "Unspecified"
        commitment = categories.get("commitment")

        posted_at = None
        created = raw.get("createdAt")
        if isinstance(created, (int, float)):
            posted_at = datetime.fromtimestamp(created / 1000, tz=timezone.utc)

        description_html = raw.get("descriptionPlain") or raw.get("description")
        description_text = (
            raw.get("descriptionPlain")
            or (_strip_html(raw["description"]) if raw.get("description") else None)
        )

        return Job(
            source="lever",
            source_id=raw["id"],
            company=company,
            title=raw["text"],
            location=JobLocation(
                raw=location_raw,
                remote="remote" in (location_raw or "").lower() or commitment == "Remote",
            ),
            url=raw["hostedUrl"],
            description_html=description_html,
            description_text=description_text,
            department=categories.get("team"),
            posted_at=posted_at,
        )