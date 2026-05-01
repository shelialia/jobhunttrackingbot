import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemma-4-31b-it")
_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
}

_PROMPT_TEMPLATE = """You are a job application email classifier.

You must return EXACTLY ONE valid JSON object matching the schema below.
Do not include explanations, reasoning, bullet points, markdown, code fences, labels, or any text before or after the JSON object.
If you output anything other than the JSON object, the response is invalid.

Output schema:
{{
  "type": "oa | hirevue | interview | application | offer | rejection | irrelevant",
  "company": "<string or null>",
  "role": "<string or null>",
  "deadline": "<ISO8601 datetime or null>",
  "link": "<URL string or null>",
  "confidence": <float 0-1>
}}

Rules:
- type = "application"  → a job application confirmation / acknowledgement email (you applied and they confirmed receipt)
- type = "oa"           → an online assessment / coding challenge invite sent during the hiring process.
                          Platforms include: HackerRank, Codility, CoderPad, CodeSignal, HackerEarth,
                          TestGorilla, Karat, Qualified, iMocha, SHL, Pymetrics, Vervoe, Mercer Mettl,
                          Arctic Shores, Aon/cut-e, Indeed Assessments, or any email asking you to
                          complete a timed coding test, technical screen, or skills assessment.
- type = "hirevue"      → a one-way video interview invite (HireVue, Spark Hire, Modern Hire, Montage,
                          or any platform asking you to record video answers to pre-set questions)
- type = "interview"    → a live interview invite (phone / virtual / on-site) sent during the hiring process
- type = "offer"        → an offer email from the company (verbal or written offer, offer letter, compensation details, next steps to accept)
- type = "rejection"    → a rejection / regret email from the company (not moving forward, application unsuccessful, position filled, "unfortunately")
- type = "irrelevant"   → classify as irrelevant if ANY of the following are true:
    * not related to a job application
    * the role has already been accepted / offer signed (onboarding, team matching, intern intro calls, mentor meetings, pre-start logistics)
    * a general newsletter, recruiter outreach, or job alert (not a specific application response)
    * a scheduling email for a meeting that is NOT part of an active interview process (e.g. intern orientation, team intro)
- deadline: if an exact date/time is given, convert it to ISO 8601 UTC. If a relative window is given (e.g. "you have 7 days", "complete within 1 week"), calculate the absolute deadline by adding that duration to the email received date provided below. Return null only if no deadline information is present at all.
- link: the direct assessment or meeting URL if present; null otherwise
- confidence: your confidence in the classification (0-1)

Key distinction: only classify emails that are part of an ACTIVE, PENDING application process. Post-acceptance emails (team matching updates, onboarding, intro calls with future colleagues/mentors) are irrelevant.

Email received date (UTC): {email_date}
Subject: {subject}

Body:
{body}"""


def _extract_response_text(response) -> str:
    chunks: list[str] = []

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", []) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text is None and hasattr(part, "get"):
                text = part.get("text")
            if text:
                chunks.append(text)

    if chunks:
        return "".join(chunks).strip()

    try:
        return response.text.strip()
    except Exception as exc:
        raise ValueError(f"Model returned no readable text parts: {response}") from exc


def _parse_json_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No JSON object found in model response", text, 0)


def classify_email(subject: str, body: str, email_date: str | None = None) -> dict:
    print(f"\n{'='*60}")
    print(f"SUBJECT : {subject}")
    print(f"BODY    : {body[:300]!r}")
    print(f"{'='*60}")

    prompt = _PROMPT_TEMPLATE.format(
        subject=subject,
        body=body,
        email_date=email_date or "unknown",
    )
    response = _model.generate_content(prompt, generation_config=_GENERATION_CONFIG)
    text = _extract_response_text(response)

    print(f"GEMINI  : {text}")
    print(f"{'='*60}\n")

    # Strip accidental markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    payload = _parse_json_response(text)
    print(f"PARSED  : {json.dumps(payload, ensure_ascii=False)}")
    return payload
