"""Seed the demo SQLite database with sample jobs, scores, and drafts.

Run from project root:
    python -m demo.seed

This creates demo/jobcopilot.db with ~25 sample jobs across multiple
fake companies, with realistic match scores and assessments. Safe to
re-run — it drops and recreates the demo DB each time.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


DEMO_DB = Path("demo/jobcopilot.db")
DEMO_DRAFTS = Path("demo/drafts")


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    dedup_key       TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    location_raw    TEXT NOT NULL,
    remote          INTEGER NOT NULL,
    country         TEXT,
    url             TEXT NOT NULL,
    description     TEXT,
    department      TEXT,
    posted_at       TEXT,
    fetched_at      TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    application_status TEXT DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS match_scores (
    dedup_key       TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    model           TEXT NOT NULL,
    score           INTEGER NOT NULL,
    tier            TEXT NOT NULL,
    result_json     TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL    NOT NULL DEFAULT 0.0,
    scored_at       TEXT    NOT NULL,
    PRIMARY KEY (dedup_key, prompt_version, model)
);
"""


# Fake companies — realistic but clearly not real
COMPANIES = [
    "FrontierAI Labs",
    "AlphaScale",
    "BetaCloud",
    "GammaCorp",
    "DeltaScale AI",
    "NovaPlatform",
    "OrbitData",
    "PrismHealth",
]


# Sample jobs with realistic titles and descriptions
SAMPLE_JOBS = [
    # ---- STRONG MATCHES (82-85) ----
    {
        "company": "FrontierAI Labs",
        "title": "Senior GenAI Backend Engineer, Platform",
        "location": "San Francisco, CA | Remote - USA",
        "remote": True,
        "score": 85,
        "tier": "strong_match",
        "one_liner": "Direct fit: senior Python backend with deep GenAI/LangChain/RAG experience matches an AI platform team scaling LLM workloads.",
        "strengths": [
            "6+ years Python with FastAPI, async, and production microservices",
            "Hands-on experience with LangChain, LangGraph, RAG, and AWS Bedrock",
            "Proven track record shipping high-throughput AI services (600K+ daily calls)",
            "Strong infrastructure foundation: Kubernetes, Terraform, Redis"
        ],
        "gaps": [
            "No explicit experience with the team's specific vector DB (Qdrant)",
            "No prior open-source contributions to LangChain ecosystem mentioned"
        ],
        "red_flags": [],
        "description": "We're building the AI platform that powers conversational agents across the enterprise. You'll design and ship FastAPI microservices, optimize LLM inference pipelines, and architect multi-agent workflows using LangGraph. Strong Python (async, FastAPI), production LLM experience (RAG, agents, evals), and infrastructure depth (Docker, Kubernetes, AWS or Azure) required.",
        "days_ago": 1,
    },
    {
        "company": "AlphaScale",
        "title": "Staff Software Engineer, AI Infrastructure",
        "location": "Remote - USA",
        "remote": True,
        "score": 82,
        "tier": "good_match",
        "one_liner": "Senior Python/AI background aligns with an infrastructure-heavy Staff role; modest gap on staff-level org leadership.",
        "strengths": [
            "Deep Python and FastAPI production experience",
            "Hybrid RAG pipeline architecture using LangChain and multiple vector stores",
            "Performance optimization track record (18% latency reduction, 25% CPU savings)",
            "Mentoring experience with junior engineers"
        ],
        "gaps": [
            "Limited evidence of Staff-level org-wide technical leadership",
            "No explicit experience driving multi-team initiatives"
        ],
        "red_flags": [],
        "description": "Lead the design of our AI infrastructure layer: model serving, request routing, and cost optimization. Staff-level role requires 8+ years of backend engineering with significant production LLM/ML experience. Must have shipped large-scale Python services on Kubernetes. Track record of driving technical strategy across teams.",
        "days_ago": 2,
    },
    {
        "company": "BetaCloud",
        "title": "Senior Backend Engineer, Applied AI",
        "location": "New York, NY",
        "remote": False,
        "score": 82,
        "tier": "good_match",
        "one_liner": "Strong Python backend + LLM applied experience; missing some payments domain expertise.",
        "strengths": [
            "Senior Python with FastAPI, async, and high-throughput service design",
            "RAG pipelines and LLM integration experience (LangChain, Bedrock)",
            "Production deployment expertise (Docker, Kubernetes, EKS)",
            "Performance tuning and observability with OpenTelemetry"
        ],
        "gaps": [
            "No explicit fintech or payments domain experience",
            "Limited evidence of customer-facing technical communication"
        ],
        "red_flags": [],
        "description": "Build production AI features for our payments platform. We need a backend engineer who can ship FastAPI services, integrate LLMs (Claude, GPT), and design async data pipelines. 5+ years Python required. Bonus: experience with PCI-compliant systems or financial data.",
        "days_ago": 3,
    },
    {
        "company": "DeltaScale AI",
        "title": "Applied AI Engineer, Enterprise Agents",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 82,
        "tier": "good_match",
        "one_liner": "Hands-on agentic AI and RAG experience strongly aligns with applied agent engineering for enterprise.",
        "strengths": [
            "LangGraph multi-step agent workflow implementation in production",
            "Hybrid RAG retrieval pipeline design (LangChain, LlamaIndex, vector stores)",
            "Enterprise-domain exposure with regulated environments",
            "API design and async Python depth"
        ],
        "gaps": [
            "No customer-facing or pre-sales experience",
            "Limited demonstration of enterprise account engagement"
        ],
        "red_flags": [],
        "description": "Design and ship AI agents that solve real enterprise workflows. You'll architect multi-step agent flows, build evaluation frameworks, and partner closely with customers on integration. Python + LangGraph/LangChain + production LLM experience essential.",
        "days_ago": 1,
    },
    # ---- GOOD MATCHES (78-81) ----
    {
        "company": "NovaPlatform",
        "title": "Senior Software Engineer",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 78,
        "tier": "good_match",
        "one_liner": "Senior Python backend with strong distributed systems experience; minor stack gap (Go).",
        "strengths": [
            "Senior Python with strong production track record",
            "Distributed systems and microservices design",
            "AWS and Azure cloud deployment experience",
            "CI/CD pipeline expertise (Jenkins, GitHub Actions)"
        ],
        "gaps": [
            "Go programming experience preferred but not on resume",
            "No explicit experience with their specific event streaming stack"
        ],
        "red_flags": [],
        "description": "Build scalable backend services for our developer platform. Looking for senior engineers with deep Python (or Go) experience, distributed systems fluency, and a track record of shipping production-grade APIs.",
        "days_ago": 4,
    },
    {
        "company": "AlphaScale",
        "title": "Senior Software Engineer, AI Products",
        "location": "Remote - USA",
        "remote": True,
        "score": 78,
        "tier": "good_match",
        "one_liner": "Strong Python, AI/LLM, and backend expertise; missing frontend depth and consumer product scale experience.",
        "strengths": [
            "Production LLM integration experience (LangChain, Bedrock)",
            "Senior Python backend track record",
            "Full-stack capability with async API design",
            "Track record of shipping AI features end-to-end"
        ],
        "gaps": [
            "Limited frontend/TypeScript depth shown on resume",
            "No consumer product (B2C) scale experience"
        ],
        "red_flags": [],
        "description": "Ship AI-powered features for our consumer product. Need a full-stack-capable engineer comfortable with Python backend and TypeScript/React frontend. Production LLM experience (RAG, prompt engineering, evals) is strongly preferred.",
        "days_ago": 2,
    },
    {
        "company": "OrbitData",
        "title": "Senior Software Engineer, Backend — Frontier Data",
        "location": "New York, NY",
        "remote": False,
        "score": 78,
        "tier": "good_match",
        "one_liner": "Strong Python + data pipeline experience aligns with a senior backend role on a data-heavy team.",
        "strengths": [
            "Data pipeline architecture (Pandas, NumPy, DBT)",
            "Production Python with SQLAlchemy and PostgreSQL",
            "AWS deployment expertise",
            "Performance tuning at the query and service layer"
        ],
        "gaps": [
            "Limited experience with petabyte-scale streaming systems",
            "No explicit Kafka or Spark production experience"
        ],
        "red_flags": [],
        "description": "Join our Frontier Data team. Design and ship backend services that process and serve high-volume data feeds to AI systems. Strong Python required, plus experience with data infrastructure (warehouses, streaming, ETL).",
        "days_ago": 5,
    },
    {
        "company": "DeltaScale AI",
        "title": "Applied AI Engineer, Enterprise GenAI",
        "location": "San Francisco, CA | New York, NY",
        "remote": False,
        "score": 78,
        "tier": "good_match",
        "one_liner": "Direct hands-on GenAI engineering match; minor seniority gap for the specific staff-level scope.",
        "strengths": [
            "Production LangChain + RAG pipeline experience",
            "Multi-agent workflow design with LangGraph",
            "Enterprise-domain background with regulated systems",
            "Python backend depth"
        ],
        "gaps": [
            "Position is staff-level by listing; candidate is senior-level",
            "Limited customer workshop or enterprise engagement evidence"
        ],
        "red_flags": [],
        "description": "Ship LLM-powered solutions for enterprise customers. Build agentic workflows, RAG systems, and evaluation frameworks. Partner with customers to translate business needs into AI products. Python + LangChain + production LLM experience required.",
        "days_ago": 3,
    },
    # ---- STRETCH MATCHES (70-77) ----
    {
        "company": "GammaCorp",
        "title": "Staff Software Engineer, Platform",
        "location": "Seattle, WA",
        "remote": False,
        "score": 74,
        "tier": "stretch",
        "one_liner": "Solid platform engineering background; staff-level scope is a stretch given current experience level.",
        "strengths": [
            "Modern cloud-native stack (Kubernetes, Helm, Terraform)",
            "Strong Python backend foundation",
            "Production microservices design",
            "CI/CD and observability experience"
        ],
        "gaps": [
            "Staff role typically expects 8-10+ years; candidate is at ~6",
            "Limited demonstration of cross-team technical leadership",
            "No explicit large-scale infrastructure design ownership"
        ],
        "red_flags": [],
        "description": "Drive technical strategy for our platform team. Staff-level role: 8+ years of backend engineering, demonstrated ability to lead architecture decisions across teams, and a track record of shipping platform-level services at scale.",
        "days_ago": 6,
    },
    {
        "company": "PrismHealth",
        "title": "Senior Software Engineer, Clinical Data Platform",
        "location": "Remote - USA",
        "remote": True,
        "score": 76,
        "tier": "stretch",
        "one_liner": "Healthcare AI background aligns; HL7/FHIR specialty knowledge would strengthen the match.",
        "strengths": [
            "PHI-compliant Python pipeline experience",
            "Clinical document processing background",
            "Production FastAPI with OAuth2/JWT for healthcare APIs",
            "AWS Bedrock integration for clinical text"
        ],
        "gaps": [
            "No explicit HL7 or FHIR standard experience",
            "Limited evidence of EHR system integration"
        ],
        "red_flags": [],
        "description": "Build the data platform that powers our clinical AI products. HIPAA-regulated environment. Need senior Python engineer with healthcare data experience, ideally with HL7/FHIR knowledge and EHR integration background.",
        "days_ago": 4,
    },
    {
        "company": "NovaPlatform",
        "title": "Backend Engineer, Developer Experience",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 72,
        "tier": "stretch",
        "one_liner": "Strong backend foundation; role focuses on developer-tooling product sense which is less evidenced.",
        "strengths": [
            "Senior Python with API design expertise",
            "Mentoring and code review experience",
            "Modern stack including FastAPI and async patterns",
            "CI/CD pipeline construction"
        ],
        "gaps": [
            "Limited evidence of developer-experience product thinking",
            "No SDK or developer-tooling product work shown"
        ],
        "red_flags": [],
        "description": "Build APIs and SDKs that developers love. Looking for backend engineers with strong product sense for developer experience. Senior Python, REST/GraphQL design, and clean API patterns required.",
        "days_ago": 3,
    },
    {
        "company": "FrontierAI Labs",
        "title": "Senior Full-Stack Engineer, Education",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 72,
        "tier": "stretch",
        "one_liner": "Backend match is strong; frontend depth and domain experience in EdTech are gaps.",
        "strengths": [
            "Senior Python backend with modern frameworks",
            "API design and async patterns",
            "Production deployment expertise",
            "LLM integration experience"
        ],
        "gaps": [
            "Limited frontend/React depth on resume",
            "No education domain experience shown",
            "Less evidence of full-stack feature ownership"
        ],
        "red_flags": [],
        "description": "Build educational tools powered by AI. Full-stack role: Python backend (FastAPI), React frontend, and a heart for education products. Senior level: 5+ years total experience required.",
        "days_ago": 5,
    },
    {
        "company": "OrbitData",
        "title": "ML Engineer, Recommendation Systems",
        "location": "Remote - USA",
        "remote": True,
        "score": 72,
        "tier": "stretch",
        "one_liner": "Strong AI/LLM background; classical ML modeling experience for recsys is a real gap.",
        "strengths": [
            "Production LLM integration experience",
            "Python data pipeline expertise",
            "Vector store and embedding work (Pinecone, Weaviate)",
            "AWS infrastructure depth"
        ],
        "gaps": [
            "No explicit recommendation system modeling experience",
            "Limited classical ML (XGBoost, ranking models) on resume",
            "No A/B testing framework experience shown"
        ],
        "red_flags": [],
        "description": "Build the recommendation engine that powers our product. Need an ML engineer with production recommendation system experience: feature engineering, ranking models, A/B testing, and online evaluation.",
        "days_ago": 7,
    },
    {
        "company": "AlphaScale",
        "title": "Senior Security Engineer, AI Safety",
        "location": "Remote - USA",
        "remote": True,
        "score": 70,
        "tier": "stretch",
        "one_liner": "Strong Python and platform engineering; AI safety / red-teaming specialty is the gap.",
        "strengths": [
            "Backend Python with OAuth2/JWT and RBAC experience",
            "Production AWS deployment with secrets management",
            "LLM integration knowledge",
            "Observability and logging practices"
        ],
        "gaps": [
            "No explicit AI red-teaming or jailbreak research experience",
            "Limited security engineering specialty work",
            "No CVE disclosures or security publications"
        ],
        "red_flags": [],
        "description": "Build the security layer protecting our AI systems. Red-team prompts, detect jailbreaks, design input/output filters. Backend security engineering background plus deep curiosity about AI safety required.",
        "days_ago": 6,
    },
    # ---- POOR MATCHES (40-65) ----
    {
        "company": "BetaCloud",
        "title": "Senior iOS Software Engineer",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 12,
        "tier": "skip",
        "one_liner": "iOS role is outside the candidate's Python backend stack.",
        "strengths": [
            "Strong engineering fundamentals",
            "Production deployment experience"
        ],
        "gaps": [
            "No iOS, Swift, or Objective-C experience",
            "No mobile development background",
            "Entire career has been backend Python"
        ],
        "red_flags": [
            "Role is fundamentally outside candidate's stack — iOS development requires years of mobile-specific expertise"
        ],
        "description": "Lead iOS development for our flagship app. Senior Swift and SwiftUI required. 5+ years iOS production experience.",
        "days_ago": 4,
    },
    {
        "company": "GammaCorp",
        "title": "Software Engineer Intern (Summer)",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 8,
        "tier": "skip",
        "one_liner": "Intern role; candidate is a senior with 6+ years of experience.",
        "strengths": [],
        "gaps": [
            "Internship requires student status",
            "Major seniority mismatch — candidate has 6+ years of professional experience"
        ],
        "red_flags": [
            "Senior engineer applying to an intern role would be flagged immediately by recruiters"
        ],
        "description": "Summer internship for current undergraduate students. Computer Science majors in their junior or senior year preferred.",
        "days_ago": 8,
    },
    {
        "company": "DeltaScale AI",
        "title": "Engineering Manager, Platform",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 52,
        "tier": "poor_match",
        "one_liner": "Strong individual contributor background but no people-management experience yet.",
        "strengths": [
            "Senior backend engineering depth",
            "Mentoring junior engineers experience",
            "Cross-functional collaboration"
        ],
        "gaps": [
            "No prior people-management or direct reports experience",
            "EM roles typically expect 3+ years of management",
            "Limited evidence of hiring or performance management"
        ],
        "red_flags": [
            "Role is fundamentally management, not IC engineering"
        ],
        "description": "Lead our platform engineering team. Looking for proven engineering managers with experience scaling teams, hiring, performance management, and driving technical strategy. 3+ years of management required.",
        "days_ago": 5,
    },
    {
        "company": "NovaPlatform",
        "title": "Staff Data Engineer",
        "location": "Seattle, WA",
        "remote": False,
        "score": 58,
        "tier": "poor_match",
        "one_liner": "Some data engineering exposure but lacks Staff-level data infrastructure depth at scale.",
        "strengths": [
            "Python data pipeline experience with Pandas",
            "SQL and ETL knowledge",
            "Cloud deployment background"
        ],
        "gaps": [
            "No production Spark, Flink, or Kafka experience",
            "Limited petabyte-scale data work shown",
            "No data platform architecture ownership"
        ],
        "red_flags": [],
        "description": "Staff Data Engineer to architect our data infrastructure. Spark, Flink, Kafka required. 8+ years of data engineering with proven petabyte-scale system design.",
        "days_ago": 6,
    },
    {
        "company": "PrismHealth",
        "title": "Director of Engineering",
        "location": "Boston, MA",
        "remote": False,
        "score": 32,
        "tier": "skip",
        "one_liner": "Director role expects 10+ years and substantial management — candidate is senior IC.",
        "strengths": [
            "Senior engineering background",
            "Mentoring experience"
        ],
        "gaps": [
            "Director roles expect 10+ years; candidate has ~6",
            "No people-management experience",
            "No prior engineering leadership role"
        ],
        "red_flags": [
            "Major seniority mismatch — applying to Director from senior IC level"
        ],
        "description": "Director of Engineering leading multiple teams. 10+ years experience required, with 5+ years in management. Proven track record of scaling engineering organizations.",
        "days_ago": 7,
    },
    # ---- A few more mid-range ----
    {
        "company": "FrontierAI Labs",
        "title": "Software Engineer, Inference Optimization",
        "location": "San Francisco, CA",
        "remote": False,
        "score": 68,
        "tier": "stretch",
        "one_liner": "Backend engineering match is decent; inference-specific optimization specialty is the gap.",
        "strengths": [
            "Production LLM integration experience",
            "Performance tuning track record (latency, CPU)",
            "Python and async expertise"
        ],
        "gaps": [
            "No explicit GPU optimization or CUDA experience",
            "Limited model serving framework expertise (vLLM, TGI)",
            "No model quantization or compilation work shown"
        ],
        "red_flags": [],
        "description": "Optimize LLM inference for our production fleet. GPU optimization, model quantization, and inference framework expertise (vLLM, TGI) required.",
        "days_ago": 3,
    },
    {
        "company": "AlphaScale",
        "title": "Senior Software Engineer, Search Infrastructure",
        "location": "Remote - USA",
        "remote": True,
        "score": 70,
        "tier": "stretch",
        "one_liner": "Vector search and RAG experience aligns; classical search infrastructure (Elasticsearch, Lucene) is the gap.",
        "strengths": [
            "Production RAG pipeline experience",
            "Vector store work (Pinecone, Weaviate)",
            "Embedding strategy and retrieval tuning",
            "Senior Python backend depth"
        ],
        "gaps": [
            "No production Elasticsearch or Lucene experience",
            "Limited classical search ranking work",
            "No experience with query understanding pipelines"
        ],
        "red_flags": [],
        "description": "Build search infrastructure powering our products. Mix of classical search (Elasticsearch) and modern vector search (RAG). Senior backend with search experience required.",
        "days_ago": 4,
    },
    {
        "company": "BetaCloud",
        "title": "Senior Backend Engineer, Internal Tools",
        "location": "New York, NY",
        "remote": False,
        "score": 70,
        "tier": "stretch",
        "one_liner": "Backend match is good; specific internal-tools product experience is less evidenced.",
        "strengths": [
            "Senior Python with FastAPI",
            "Tool-building and automation experience (JIRA API)",
            "Strong API design",
            "Mentoring junior engineers"
        ],
        "gaps": [
            "Limited evidence of internal-tools product design",
            "No experience with workflow engines (Temporal, Camunda)"
        ],
        "red_flags": [],
        "description": "Build internal tools that power our company. Senior backend with experience in workflow engines (Temporal, Airflow) and tool design preferred.",
        "days_ago": 5,
    },
    {
        "company": "OrbitData",
        "title": "Backend Engineer, Streaming Platform",
        "location": "Remote - USA",
        "remote": True,
        "score": 62,
        "tier": "stretch",
        "one_liner": "Backend match is moderate; streaming-specific systems work is a meaningful gap.",
        "strengths": [
            "Senior Python with async patterns",
            "AWS infrastructure background",
            "REST/GraphQL API design"
        ],
        "gaps": [
            "No production Kafka or Pulsar experience",
            "Limited streaming data pipeline work",
            "No event-driven architecture ownership shown"
        ],
        "red_flags": [],
        "description": "Build our streaming platform. Kafka, Pulsar, or Kinesis required. Streaming-first event-driven architecture experience needed.",
        "days_ago": 6,
    },
]


def seed():
    """Drop and recreate the demo database with sample data."""
    DEMO_DB.parent.mkdir(exist_ok=True)
    if DEMO_DB.exists():
        DEMO_DB.unlink()

    conn = sqlite3.connect(DEMO_DB)
    conn.executescript(SCHEMA)

    now = datetime.utcnow()

    for i, job in enumerate(SAMPLE_JOBS):
        dedup_key = f"demo:{i+1:03d}"
        first_seen = now - timedelta(days=job["days_ago"])
        posted_at = first_seen - timedelta(hours=2)

        conn.execute(
            """
            INSERT INTO jobs (
                dedup_key, source, source_id, company, title,
                location_raw, remote, country, url,
                description, department,
                posted_at, fetched_at, first_seen_at,
                application_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dedup_key,
                "demo",
                f"{i+1:03d}",
                job["company"],
                job["title"],
                job["location_raw"] if "location_raw" in job else job["location"],
                int(job.get("remote", False)),
                "United States",
                f"https://example.com/jobs/{i+1:03d}",
                job["description"],
                None,
                posted_at.isoformat(),
                now.isoformat(),
                first_seen.isoformat(),
                "new",
            ),
        )

        # Create the match_score record
        result_json = json.dumps({
            "score": job["score"],
            "tier": job["tier"],
            "one_line_reason": job["one_liner"],
            "matching_strengths": job["strengths"],
            "skill_gaps": job["gaps"],
            "red_flags": job["red_flags"],
        })

        conn.execute(
            """
            INSERT INTO match_scores (
                dedup_key, prompt_version, model, score, tier,
                result_json, input_tokens, cache_read_tokens,
                cache_creation_tokens, output_tokens, cost_usd, scored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dedup_key, "match-v2", "claude-haiku-4-5",
                job["score"], job["tier"],
                result_json,
                1800, 0, 0, 650, 0.0050,
                first_seen.isoformat(),
            ),
        )

    conn.commit()
    conn.close()

    print(f"Seeded {len(SAMPLE_JOBS)} sample jobs to {DEMO_DB}")
    print(f"Score distribution:")
    tier_counts = {}
    for job in SAMPLE_JOBS:
        tier_counts[job["tier"]] = tier_counts.get(job["tier"], 0) + 1
    for tier, n in sorted(tier_counts.items(), key=lambda x: -x[1]):
        print(f"  {tier:14s} {n:3d}")


if __name__ == "__main__":
    seed()
