import json
import logging

from app.services.llm.base import BaseLLMProvider, LLMMessage

logger = logging.getLogger(__name__)

RESUME_SYSTEM = """You are an HR assistant. Extract structured data from the resume/CV below and return ONLY valid JSON — no prose, no markdown fences.

Output schema:
{
  "candidate_name": "<full name or null>",
  "candidate_email": "<email address found in the resume, or null>",
  "candidate_phone": "<phone number or null>",
  "education": [{"school": "", "degree": "", "major": "", "year": ""}],
  "experience": [{"company": "", "title": "", "duration": "", "summary": ""}],
  "skills": ["skill1", "skill2"],
  "desired_position": "<position the candidate is applying for, or null>",
  "expected_salary": "<expected salary text, or null>",
  "years_experience": <total years of work experience as an integer, or null>,
  "summary": "<2-3 sentence neutral assessment of the candidate>",
  "match_score": <integer 0-100 for fit against the target role, or null>,
  "match_notes": "<one sentence justifying the score>"
}

Rules:
- Reply in the SAME language as the resume.
- Use null / [] when information is genuinely absent — do NOT invent facts.
- match_score reflects fit for the target role given below (if any)."""


async def parse_resume(
    llm: BaseLLMProvider,
    resume_text: str,
    target_role: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Extract structured fields from resume text. Returns a dict following the
    schema above plus 'llm_model'. Returns {} on unrecoverable parse failure.
    """
    if not resume_text or not resume_text.strip():
        return {}

    role_hint = f"\n\nTarget role / department for match scoring: {target_role}" if target_role else ""
    content = f"Resume:\n{resume_text[:6000]}{role_hint}"
    messages = [
        LLMMessage(role="system", content=RESUME_SYSTEM),
        LLMMessage(role="user", content=content),
    ]

    resp = await llm.chat(messages, model=model, temperature=0.1, response_format="json")
    try:
        data = json.loads(resp.content)
        if not isinstance(data, dict):
            raise ValueError("resume JSON is not an object")
    except Exception as e:
        logger.warning("Resume parse JSON failed: %s | raw=%s", e, resp.content[:200])
        return {"llm_model": resp.model}

    # normalize list fields
    for key in ("education", "experience", "skills"):
        if not isinstance(data.get(key), list):
            data[key] = []
    # normalize numeric fields
    for key in ("years_experience", "match_score"):
        val = data.get(key)
        if isinstance(val, str) and val.isdigit():
            data[key] = int(val)
        elif not isinstance(val, int):
            data[key] = None

    data["llm_model"] = resp.model
    return data
