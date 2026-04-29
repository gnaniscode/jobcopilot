"""Batch-score all unscored jobs in the DB."""
import asyncio
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

from jobcopilot.matching.prefilter import should_skip
from jobcopilot.matching.prompts import PROMPT_VERSION
from jobcopilot.matching.scorer import MODEL, score_job
from jobcopilot.resume.parser import load_or_parse_resume
from jobcopilot.sources.schemas import Job, JobLocation
from jobcopilot.storage.db import JobStore


CONCURRENCY = 2
REQUEST_DELAY_SECONDS = 1.5  # space out requests to respect 50K tpm limit
MAX_BUDGET_USD = 5.00  # hard stop if cumulative cost exceeds this
SMOKE_TEST_LIMIT: int | None = None  # full run


def _row_to_job(row: dict) -> Job:
    return Job(
        source=row["source"],
        source_id=row["source_id"],
        company=row["company"],
        title=row["title"],
        location=JobLocation(
            raw=row["location_raw"],
            remote=bool(row["remote"]),
            country=row["country"],
        ),
        url=row["url"],
        description_text=row["description"],
        department=row["department"],
        posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
    )


async def _score_one(
    *,
    job: Job,
    resume,
    client: Anthropic,
    store: JobStore,
    sem: asyncio.Semaphore,
    counters: dict,
) -> None:
    if counters.get("budget_exceeded"):
        return
    async with sem:
        if counters.get("budget_exceeded"):
            return
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

        # Retry up to 3 times on rate-limit errors with exponential backoff
        last_error = None
        for attempt in range(3):
            try:
                result, telem = await asyncio.to_thread(score_job, resume, job, client=client)
                await store.save_score(
                    dedup_key=job.dedup_key,
                    prompt_version=telem["prompt_version"],
                    model=telem["model"],
                    score=result.score,
                    tier=result.tier,
                    result_json=result.model_dump_json(),
                    input_tokens=telem["input_tokens"],
                    cache_read_tokens=telem["cache_read_tokens"],
                    cache_creation_tokens=telem["cache_creation_tokens"],
                    output_tokens=telem["output_tokens"],
                    cost_usd=telem["cost_usd"],
                )
                counters["scored"] += 1
                counters["cost"] += telem["cost_usd"]
                counters["cache_read"] += telem["cache_read_tokens"]
                counters["cache_create"] += telem["cache_creation_tokens"]
                if counters["cost"] >= MAX_BUDGET_USD:
                    counters["budget_exceeded"] = True
                print(
                    f"  [{counters['scored']:4d}/{counters['total']}] "
                    f"${counters['cost']:5.2f}  "
                    f"{result.score:3d} {result.tier:14s} "
                    f"[{job.company}] {job.title[:50]}"
                )
                return  # success
            except Exception as e:
                last_error = e
                err_name = type(e).__name__
                if "RateLimitError" in err_name or "429" in str(e):
                    backoff = 30 * (2 ** attempt)  # 30s, 60s, 120s
                    print(f"  ⏳ Rate limit, waiting {backoff}s before retry ({attempt+1}/3)...")
                    await asyncio.sleep(backoff)
                    continue
                # Non-rate-limit error: don't retry
                break

        counters["errors"] += 1
        print(f"  ✗ ERROR scoring {job.dedup_key}: {type(last_error).__name__}: {str(last_error)[:120]}")

async def main() -> None:
    resume = load_or_parse_resume(Path("data/resume.docx"))

    store = JobStore()
    await store.init()

    rows = await store.list_unscored_jobs(prompt_version=PROMPT_VERSION, model=MODEL)
    print(f"Found {len(rows)} unscored jobs.\n")

    if not rows:
        print("Nothing to do. Run fetch_all to ingest more jobs first.")
        return

    # Pre-filter
    to_score: list[Job] = []
    skipped = 0
    for row in rows:
        job = _row_to_job(row)
        skip, reason = should_skip(job)
        if skip:
            skipped += 1
            await store.save_score(
                dedup_key=job.dedup_key,
                prompt_version=PROMPT_VERSION,
                model="prefilter",
                score=0,
                tier="skip",
                result_json=f'{{"prefilter_reason": "{reason}"}}',
                input_tokens=0,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
            )
            continue
        to_score.append(job)

    print(f"Pre-filtered {skipped} obvious skips. {len(to_score)} relevant jobs ready to score.\n")

    if not to_score:
        return

    if SMOKE_TEST_LIMIT is not None:
        to_score = to_score[:SMOKE_TEST_LIMIT]
        print(f"  (Smoke test mode: capped at {len(to_score)} jobs)\n")

    counters = {
        "scored": 0,
        "errors": 0,
        "cost": 0.0,
        "cache_read": 0,
        "cache_create": 0,
        "total": len(to_score),
        "budget_exceeded": False,
    }
    sem = asyncio.Semaphore(CONCURRENCY)
    client = Anthropic()  # uses ANTHROPIC_API_KEY from env

    tasks = [
        _score_one(job=job, resume=resume, client=client, store=store, sem=sem, counters=counters)
        for job in to_score
    ]
    await asyncio.gather(*tasks)

    if counters["budget_exceeded"]:
        print(f"\n  ⚠️  BUDGET CAP HIT (${MAX_BUDGET_USD:.2f}). Stopped early.")

    print(
        f"\n  Done. Scored: {counters['scored']}, "
        f"Errors: {counters['errors']}, "
        f"Total cost: ${counters['cost']:.4f}"
    )
    print(
        f"  Cache: {counters['cache_read']:,} read tokens / "
        f"{counters['cache_create']:,} write tokens"
    )


if __name__ == "__main__":
    asyncio.run(main())