"""Resume parser: PDF/DOCX -> structured Resume object using Claude."""
import json
import os
from pathlib import Path

from anthropic import Anthropic
from docx import Document
from dotenv import load_dotenv
from pypdf import PdfReader

from jobcopilot.resume.schemas import Resume

load_dotenv()

CLAUDE_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 16000  # plenty of headroom for any reasonable resume

SYSTEM_PROMPT = """You are a precise resume parser. Your job is to extract structured data from resume text and return it as valid JSON.

Critical rules:
- Extract ONLY information present in the resume. Never invent or assume data.
- For dates, use "YYYY-MM" format, or "Present" for current roles.
- Skills should be a deduplicated list (combine technical and notable soft skills).
- Achievements should be specific, quantifiable bullet points (e.g., "Reduced latency 40%").
- If a field isn't found, omit it or use null. Don't guess.
- Return ONLY valid JSON. No markdown fences. No explanation. No preamble. Start with { and end with }."""

USER_PROMPT_TEMPLATE = """Extract structured data from this resume into JSON matching the following schema:

{schema}

Resume text:
---
{resume_text}
---

Return only the JSON object."""


def extract_resume_text(file_path: Path) -> str:
    """Extract raw text from a resume file (PDF or DOCX)."""
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages).strip()
    elif suffix == ".docx":
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .pdf or .docx")

    if not text:
        raise ValueError(f"No text could be extracted from {file_path}. Is it a scanned image?")
    return text


def _strip_markdown_fences(raw: str) -> str:
    """Strip ```json ... ``` fences if Claude added them despite instructions."""
    raw = raw.strip()
    if raw.startswith("```"):
        # remove opening fence
        first_newline = raw.find("\n")
        if first_newline != -1:
            raw = raw[first_newline + 1 :]
        # remove closing fence
        if raw.endswith("```"):
            raw = raw[:-3]
    return raw.strip()


def parse_resume(file_path: Path) -> Resume:
    """Parse a resume file (PDF or DOCX) into a structured Resume object."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Check your .env file.")

    resume_text = extract_resume_text(file_path)

    client = Anthropic(api_key=api_key)
    schema_json = json.dumps(Resume.model_json_schema(), indent=2)
    user_message = USER_PROMPT_TEMPLATE.format(schema=schema_json, resume_text=resume_text)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    # Inspect why the model stopped — this is critical for debugging
    stop_reason = response.stop_reason
    raw_json = response.content[0].text

    if stop_reason == "max_tokens":
        # Save the truncated response for debugging, then fail loudly
        debug_path = Path("data/_last_failed_response.txt")
        debug_path.write_text(raw_json)
        raise RuntimeError(
            f"Claude's response hit max_tokens={MAX_TOKENS} and was truncated. "
            f"Truncated response saved to {debug_path}. "
            f"Try increasing MAX_TOKENS or using a more concise resume."
        )

    raw_json = _strip_markdown_fences(raw_json)

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        debug_path = Path("data/_last_failed_response.txt")
        debug_path.write_text(raw_json)
        raise RuntimeError(
            f"Failed to parse Claude's response as JSON: {e}. "
            f"Raw response saved to {debug_path}."
        ) from e

    return Resume.model_validate(data)


if __name__ == "__main__":
    import sys
    file = Path(sys.argv[1] if len(sys.argv) > 1 else "data/resume.pdf")
    resume = parse_resume(file)
    print(resume.model_dump_json(indent=2))