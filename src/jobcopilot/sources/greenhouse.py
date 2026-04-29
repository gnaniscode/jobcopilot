"""Greenhouse public boards API connector.

Docs: https://developers.greenhouse.io/job-board.html
Endpoint: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
"""
from collections.abc import AsyncIterator
from datetime import datetime
from html import unescape
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from jobcopilot.sources.base import JobSource 
from jobcopilot.sources.schemas import Job, JobLocation


GREENHOUSE_BASE = "https://boards-api.greenhouse.io/v1/boards"


def _strip_html(html: str) -> str:
    """Quick HTML -> text. We'll get fancier later if needed."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class GreenhouseSource(JobSource):
    name = "greenhouse"

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _fetch_payload(self, company: str) -> dict:
        url = f"{GREENHOUSE_BASE}/{company}/jobs"
        response = await self.client.get(url, params={"content": "true"}, timeout=15.0)
        response.raise_for_status()
        return response.json()

    async def fetch_jobs(self, company: str) -> AsyncIterator[Job]:
        payload = await self._fetch_payload(company)
        for job_data in payload.get("jobs", []):
            yield self._normalize(company, job_data)

    @staticmethod
    def _normalize(company: str, raw: dict) -> Job:
        location_raw = (raw.get("location") or {}).get("name") or "Unspecified"
        offices = raw.get("offices") or []
        country = offices[0].get("location") if offices and offices[0].get("location") else None

        posted_at = None
        if raw.get("updated_at"):
            try:
                posted_at = datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00"))
            except ValueError:
                pass

        description_html = raw.get("content")
        description_text = _strip_html(description_html) if description_html else None

        department = None
        depts = raw.get("departments") or []
        if depts:
            department = depts[0].get("name")

        return Job(
            source="greenhouse",
            source_id=str(raw["id"]),
            company=company,
            title=raw["title"],
            location=JobLocation(
                raw=location_raw,
                remote="remote" in location_raw.lower(),
                country=country,
            ),
            url=raw["absolute_url"],
            description_html=description_html,
            description_text=description_text,
            department=department,
            posted_at=posted_at,
        )