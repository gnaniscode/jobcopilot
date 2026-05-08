# Learning to Build a GenAI Application

## A Daily Journal — Building JobCopilot

By Gnanitha Somavarapu  
Started: April 28, 2026 · Last updated: May 7, 2026

---

# About This Journal

This is a living document. I'm writing it as I learn how to build a real GenAI application from scratch — JobCopilot, an AI assistant that reads my resume, finds matching jobs across thousands of company career pages, scores how well each one fits, and helps me apply.

I'm writing this as I go, in plain English, so future-me (and anyone else learning) can understand what each piece does and *why* it matters.

The goal isn't just to build the project. It's to actually understand every concept along the way — async, schemas, prompt caching, tool use, evaluation, deployment — well enough that I could explain them in an interview or rebuild them from scratch.

At the end, this journal will become a blog post documenting the journey. The repo is at https://github.com/gnaniscode/jobcopilot.

---

# Day 1 — Setting Up the Workshop and Parsing the Resume

**Date:** April 28, 2026

## What I Built

A clean Python project with a virtual environment, a GitHub repo with proper `.gitignore` for secrets, and a resume parser that uses Claude Haiku to turn a `.docx` file into a typed `Resume` object.

## Concepts I Learned

**Virtual environment (`.venv`)** — A private Python toolbox just for one project. Without it, dependencies from different projects fight each other.

**`.env` file** — Holds secrets like the Anthropic API key. Listed in `.gitignore` so Git refuses to commit it. Bots scan public GitHub repos within seconds for leaked keys.

**Pydantic schema** — Describes the shape of data. When Claude returns JSON, Pydantic checks every field. Bad data errors out at the boundary instead of three steps later.

**Structured extraction** — The big GenAI pattern: turn unstructured text (a resume blob) into structured data (a typed Resume object). This pattern shows up everywhere — invoices, product descriptions, emails.

**Why Claude Haiku** — Resume parsing is mechanical. Haiku is fastest, cheapest. Bigger models would be wasteful. Lesson: pick model size based on task type. Extraction = small. Reasoning = big.

## The Bug I Hit

`JSONDecodeError: Unterminated string` — Claude's response got cut off because `max_tokens=4096` was too low. Fix: bump to 16,000 AND check `response.stop_reason` on every call. Production lesson: always check stop_reason. Don't assume LLM calls succeed.

---

# Day 2 — Pulling Real Jobs from the Internet

**Date:** April 28, 2026

## What I Built

Connectors for Greenhouse and Lever public APIs, an async SQLite database that dedupes jobs across runs, a YAML config listing companies to track, and an orchestrator that fetches them all concurrently. End result: 1,246 real jobs from Anthropic, Airbnb, Stripe, and Discord in my local database.

## Concepts I Learned

**API** — A "data pipe" a service exposes for programs to read.

**Greenhouse and Lever** — Two huge ATS used by thousands of companies. Both have free public APIs. No scraping, no ToS violations.

**Strategy pattern (abstract base class)** — `JobSource` is a template. `GreenhouseSource` and `LeverSource` implement it. The rest of the code only knows about the abstract class. Tomorrow I can add LinkedIn and the orchestrator stays the same.

**Async I/O** — Network calls are 99% waiting. Sequential 5 companies = 10s. Parallel = 2s.

**Retries with exponential backoff** — `@retry(stop_after_attempt(3), wait_exponential(...))`. Production code always has this.

**SQLite** — World's smallest database. Single file. Perfect for personal projects. Stored every job with a unique `dedup_key`.

## The Bugs I Hit

**Bug 1:** `ModuleNotFoundError: No module named 'yaml'` — forgot to install pyyaml. Lesson: when you see ModuleNotFoundError, check `which python` and `which pip` first. 90% of the time, that's the cause.

**Bug 2:** Two things named `JobSource` — a type alias AND an abstract class. Got `TypeError: Cannot subclass typing.Literal`. Lesson: distinct concepts deserve distinct names.

**Bug 3:** Two files with the same content. `grep` was the hero: `grep -n "JobSource" src/jobcopilot/sources/*.py`. Lesson: when something behaves weirdly, don't trust your memory. Run grep. Trust the output.

---

# Day 3 — The Matching Engine (and Caching Optimization)

**Date:** April 28, 2026

## What I Built

A `MatchResult` Pydantic schema, a versioned and calibrated prompt, a scorer using Claude Sonnet 4.6, tool use for guaranteed structured output, and prompt caching. Smoke test on one Anthropic role correctly scored a misleading "AI Architect" pre-sales role at 38/100.

## Concepts I Learned

**Why Sonnet, not Haiku** — Resume parsing was mechanical. Job matching is judgment under uncertainty. Sonnet is dramatically better at reasoning. 3-5x more expensive but I only score each job once.

**Tool use for structured output** — Define a tool with a JSON schema. Tell Claude to "respond by calling this tool." Claude can ONLY return data matching the schema. Works ~99.9% vs ~95% for "please return JSON." This is the production-grade way.

**Calibration through prompt design** — If I just say "score 0-100," LLMs default to ~75 even for terrible matches. Explicit ranges plus hard rules ("A role explicitly outside the candidate's tech stack gets <50 even if title sounds adjacent") fix this. The prompt does real work.

**Cost tracking on every call** — Every API response includes `usage.input_tokens` and `usage.output_tokens`. Multiply by Anthropic's prices. Production teams that don't track cost go broke.

**Prompt caching** — Mark static prompt content as cacheable. First call processes normally. Subsequent calls read from cache at ~10% of normal price. For batch processing: 5-7x cheaper.

**The cache miss bug** — After enabling caching, telemetry showed `cache_read_tokens: 0`. Cache hits require byte-identical content. Every run was calling `parse_resume()` again, producing slightly different JSON each time. Fix: parse once, save to disk, reuse same bytes. Deep production lesson: deterministic caching requires deterministic inputs.

---

# Day 4 — Scaling, Drafting, Dashboard, Bugs

**Date:** May 7, 2026

## What I Built

The heaviest day yet. Almost every piece of the system came together:

- Switched matching engine from Sonnet to Haiku to fit a tight $8 project budget
- Wrote a smart prefilter with relevance whitelist + word-boundary US location matching
- Batch scored 306 jobs across multiple runs with concurrency limits, rate-limit retries, and a hard budget cap
- Expanded from 4 to 7 companies — 2,740 jobs ingested total
- Built the cover letter drafter with strict forbidden-phrase prompts
- Generated 14 tailored cover letters
- Built a Streamlit dashboard with sidebar stats, filters, expandable per-job rows, draft viewer, status updates
- Added "Last X days" filtering and on-demand draft generation

End-of-day state: ~$4.50 of $8 budget spent, 306 scored, 84 matches at 70+, 14 ready-to-edit drafts, working web UI, all committed to GitHub.

## Concepts I Learned

**Cost engineering** — Real choices, not "use a cheaper model and hope." Combined effect: a job-scoring task that would have cost ~$50 cost ~$4.50.

- Switch to Haiku for matching (3x cheaper than Sonnet)
- Aggressive prefilter — drop ~85% of jobs before paying for LLM scoring
- Description truncation — cap at 2,000 chars from 6,000
- Smaller schemas — flatter Pydantic models = more reliable on Haiku
- Hard budget cap — `MAX_BUDGET_USD = 5.00`
- Smoke test before batch — score 5 jobs first, multiply to estimate

**Rate limiting at the LLM layer** — Anthropic enforces both requests/min AND input tokens/min (50K TPM on my tier). Each scoring call sends ~5,000 tokens. Math: 50,000 ÷ 5,000 = 10 calls/minute MAX. So 150 jobs = 15 minutes minimum. Forced me to drop concurrency from 5 to 2, add 1.5s pacing, and build retry-with-backoff that catches `RateLimitError`. Real production lesson: rate-limit awareness is part of LLM architecture, not an afterthought.

**Word-boundary matching vs substring matching** — My prefilter used substring matching. The string `", ca"` was meant to match California ("San Francisco, CA"). But `, ca` is also a substring of `, Canada`. So 226 Toronto/Canadian jobs got scored (wasted ~$1.80). Fix: regex with word boundaries plus a hard exclusion list of non-US country names. Lesson: substring matching is naive. Real data reveals what unit tests miss.

**Prompt versioning** — Every prompt has a version constant. `match_scores` table has composite primary key on `(dedup_key, prompt_version, model)`. Bumping the version means new scores get computed cleanly without overwriting old ones. Without versioning, this would be chaos.

**Forbidden-phrase rules** — First version of the cover letter prompt produced "passionate" and "I would love" all over. Added a strict forbidden-phrase list. Compliance jumped from ~70% to ~93% (still got one "wheelhouse" leak in 14 drafts). Lesson: prompts are guidelines, not guarantees. Even with explicit rules, smaller models slip ~5-10%.

**Streamlit as the right tool** — A backend engineer can ship a working UI in 200 lines of Python. No HTML/CSS/JS. For a portfolio piece, the speed-to-shipped is worth the customization tradeoff.

**Idempotency matters** — Every run of `fetch_all` skips jobs already in DB. Every run of `batch` skips jobs already scored. Every run of the drafter skips jobs whose markdown file already exists. Idempotent commands let you re-run without fear, which is huge when iterating.

**`cat > file << EOF` for reliable file writes** — VS Code's "save" silently failed on me twice today (lost edits, ran the script with old code, wasted API spend). The terminal heredoc bypasses VS Code entirely. When something seems wrong, write the file from terminal and verify with `grep`.

## Bugs I Hit Today

**Bug 1 — Schema too complex for Haiku.** 7-field schema with nested lists. Haiku failed validation ~10%. Fix: simplified to 5 flat fields, added a single retry. Compliance went to ~99%.

**Bug 2 — `match_scores` table didn't exist.** Updated `db.py` schema but `JobStore.list_unscored_jobs()` was missing. Fix: rewrote the file from terminal with all methods. Verified with `grep -cE "async def" db.py`.

**Bug 3 — Indentation lost on paste.** Pasted methods into `db.py` from VS Code, indentation got mangled. Got `IndentationError`. Fix: terminal heredoc.

**Bug 4 — Cache reads stuck at 0.** Spent 30 minutes debugging. Probably account-level (caching may not be enabled for my account/region). Pragmatic call: shipped without caching, $1.30 instead of $0.50, well within budget. Senior-engineer move: stop optimizing when it stops paying off.

**Bug 5 — Toronto, Canada false positives.** Substring `, ca` matched both California and Canada. 226 wasted scores. Cleaned up bad data, bumped prompt version, moved on.

**Bug 6 — Saved file claiming "draft-v1".** Edited `prompts.py`, hit Cmd+S, but `grep` still showed v1. File appeared saved but wasn't. Re-ran the regen with the unchanged v1 prompt — paid $0.15 for nothing. Permanent rule: after editing any prompt file, run `grep` to verify the change before running an expensive batch.

---

# What's Next

## Tomorrow (Day 5) — Polish JobCopilot for Portfolio (~7 hours)

1. Take a clean dashboard screenshot, save to `docs/dashboard.png`
2. Draw a simple architecture diagram in Excalidraw, save to `docs/architecture.png`
3. Write a great README — problem, demo image, architecture, engineering decisions, lessons learned, cost analysis, tech stack, run-locally
4. Build a tiny eval set — 15 jobs scored manually, compare to Claude's scores
5. Add Evaluation section to README
6. Final commit and push
7. Optional: blog post draft (use this journal as source)
8. Optional: deploy dashboard to Streamlit Cloud (free) for live demo
9. Share on LinkedIn

By end of Day 5: JobCopilot is portfolio-grade and ready to share.

## Days 6+ — Customer Support Agent (the bigger build)

A multi-agent customer support system. Real product pattern (Intercom Fin, Sierra, Decagon do this). Demonstrates production agentic AI at scale and answers "how would you handle 100K req/sec?" interview questions.

**Why it beats JobCopilot for portfolio:** JobCopilot was a personal tool with simple flow. The support agent has agents calling agents, streaming, memory, evals, observability — every production GenAI pattern in one project.

**Production patterns I'll learn:**

- Multi-agent orchestration (router, specialists, quality eval, handoffs)
- Streaming responses (SSE from FastAPI)
- Tool use at scale
- RAG over past conversations
- Memory (Redis short-term, Postgres long-term)
- Observability (Langfuse/LangSmith)
- Evaluation (golden dataset, LLM-as-judge, regression tests)
- Caching (semantic + prompt cache)
- Rate limiting per-user
- Async + queueing (Celery/RQ/Arq)
- Guardrails (input/output filtering, prompt injection)
- Cost controls per-tenant
- Deployment (Docker, Postgres, Redis, vector DB)

**4-week build plan, 50-70 hours total:**

- Week 1: Core agent (single agent, FastAPI streaming, mock backend, basic logging)
- Week 2: Multi-agent + RAG (router + 2 specialists, pgvector, conversation memory)
- Week 3: Production hardening (eval harness, rate limiting, caching, guardrails)
- Week 4: Scale demonstration (Locust load testing, latency curves, deploy to Render/Fly.io)

**How to answer "100K req/sec" in interviews:**

Real systems handle high traffic by ensuring most requests never reach the LLM. The LLM is the expensive part. Layers:

1. CDN / edge cache for static responses (~80% of traffic)
2. Application cache (Redis with semantic key matching, ~15%)
3. Lightweight router (small model decides if LLM is needed, ~3%)
4. LLM generation (only ~2% of original traffic)
5. Async background processing (queues for long agent loops)
6. Horizontal scaling (stateless API workers behind load balancer)
7. Rate limiting + backpressure (token buckets per tenant)
8. Database (Postgres for transactional, vector DB for embeddings, both sharded)
9. Provider redundancy (failover Anthropic → smaller model or different provider)

The math: LLM provider rate limits are usually 50K-2M TPM. At 5K input tokens/req, that's ~10-400 req/sec. The LLM is the bottleneck, not the API server. Solutions: prompt caching (5-10x throughput), model downgrade for routing, batch API for non-realtime, multi-provider fanout.

After building this, I'll have experiential answers to: how do you reduce latency, how do you measure quality, how do you handle prompt injection, what's your cost-per-request, how would you A/B test prompts, how do you handle tool failures, how do you do agent handoffs.

---

# Glossary

**Agent** — An LLM-powered system that uses tools, makes decisions, takes actions toward a goal.

**API** — A data pipe a service exposes for programs to read.

**Async / asyncio** — Python's tool for doing things in parallel while waiting on I/O.

**Backoff** — Waiting longer between retries. Exponential = doubles each time.

**Cache hit / miss** — When the LLM API can reuse cached prompt content (hit, cheap) vs. reprocesses (miss, full price).

**Cron / launchd** — Scheduler that runs commands on a fixed schedule.

**dedup_key** — Unique string used as primary key to prevent duplicates.

**Eval / evaluation** — Measuring whether the LLM produces good outputs.

**Idempotent** — A command that can run multiple times without changing the outcome past the first run.

**LLM-as-judge** — Using one LLM to evaluate another's output. Cheap way to scale evaluation.

**Pydantic** — Library for defining and validating data shapes.

**Prompt caching** — Mark static prompt content as cacheable; subsequent calls reuse it at ~10% of normal cost.

**Prompt injection** — Attack where user input contains instructions to override the system prompt.

**RAG** — Retrieval-Augmented Generation. Find relevant docs, stuff into prompt before LLM call.

**Rate limit** — Cap on how many requests/tokens you can send per minute.

**Schema** — Formal description of the shape of data.

**Semantic cache** — Cache that matches similar (not identical) requests.

**Strategy pattern** — Abstract base class + plug-in implementations.

**stop_reason** — Field on every Claude response: end_turn, max_tokens, tool_use.

**Streaming** — Sending the LLM's response token-by-token as generated.

**Structured extraction** — Using an LLM to turn unstructured text into typed data.

**Tool use** — Anthropic feature: define a tool with a JSON schema, force Claude to call it. Forces structured output.

**TPM (Tokens Per Minute)** — Anthropic rate limit. Usually the binding constraint.

**Virtual environment (.venv)** — Private Python toolbox per project.

---

# Resources

- Anthropic API docs — https://docs.claude.com
- Pydantic docs — https://docs.pydantic.dev
- httpx docs — https://www.python-httpx.org
- Greenhouse public API — https://developers.greenhouse.io/job-board.html
- Lever public API — https://help.lever.co/hc/en-us/articles/360032977292
- Streamlit docs — https://docs.streamlit.io
- Karpathy Neural Networks Zero to Hero — https://karpathy.ai/zero-to-hero.html
- Hugging Face LLM Course — https://huggingface.co/learn/llm-course
- Maxime Labonne LLM Course — https://github.com/mlabonne/llm-course
- Hamel Husain (LLM evals) — https://hamel.dev/
- Eugene Yan (applied ML) — https://eugeneyan.com/writing/
- LangGraph docs — https://langchain-ai.github.io/langgraph/
- Locust load testing — https://locust.io

---

# At the End — What This Will Become

When the polish work and the support agent build are done, this becomes:

1. A blog post — "I built an AI job application assistant in a day. Here are 7 production GenAI lessons I learned."
2. A second blog post — "Building a production-grade multi-agent customer support system: architecture decisions and what I learned about scaling LLM workloads."
3. Two GitHub repos that recruiters can scan in 30 seconds and immediately understand my engineering capability.
4. A LinkedIn post sharing both — the kind of build-in-public content that puts me on recruiters' radars.
5. Interview answers grounded in real experience.

Goal: by end of June 2026, I should be the candidate who has actually built and deployed end-to-end production agentic AI systems. Not "I can explain the concepts" — I can show the code, the bugs I fixed, and the cost numbers from real deployment.

JobCopilot was the warm-up. The support agent is the real demonstration.
