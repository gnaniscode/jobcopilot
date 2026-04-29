"""Fetch all configured companies and store new jobs in SQLite.

Usage:
    python -m jobcopilot.sources.fetch_all
"""
import asyncio
from pathlib import Path

import httpx
import yaml

from jobcopilot.sources.greenhouse import GreenhouseSource
from jobcopilot.sources.lever import LeverSource
from jobcopilot.storage.db import JobStore


CONFIG_PATH = Path("config/companies.yaml")


async def fetch_company(source, company: str, store: JobStore) -> tuple[int, int]:
    """Returns (new_count, total_seen)."""
    new_count = 0
    total = 0
    try:
        async for job in source.fetch_jobs(company):
            total += 1
            if await store.upsert(job):
                new_count += 1
    except httpx.HTTPStatusError as e:
        print(f"  ✗ {source.name}/{company}: HTTP {e.response.status_code}")
        return 0, 0
    except Exception as e:
        print(f"  ✗ {source.name}/{company}: {type(e).__name__}: {e}")
        return 0, 0
    print(f"  ✓ {source.name}/{company}: {new_count} new, {total} total")
    return new_count, total


async def main() -> None:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    store = JobStore()
    await store.init()

    async with httpx.AsyncClient() as client:
        sources = {
            "greenhouse": GreenhouseSource(client),
            "lever": LeverSource(client),
        }

        tasks = []
        for entry in config["companies"]:
            source_name = entry["source"]
            slug = entry["slug"]
            source = sources.get(source_name)
            if source is None:
                print(f"  ✗ unknown source: {source_name}")
                continue
            tasks.append(fetch_company(source, slug, store))

        results = await asyncio.gather(*tasks)

    new_total = sum(r[0] for r in results)
    seen_total = sum(r[1] for r in results)
    db_total = await store.count()
    print(f"\n  Summary: {new_total} new jobs, {seen_total} seen this run, {db_total} in DB total")


if __name__ == "__main__":
    asyncio.run(main())