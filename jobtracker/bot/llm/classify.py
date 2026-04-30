import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.0-flash")

_PROMPT_TEMPLATE = """You are a job application email classifier. Analyse the email below and return ONLY valid JSON — no preamble, no markdown fences.

Output schema:
{{
  "type": "oa | hirevue | interview | application | irrelevant",
  "company": "<string or null>",
  "role": "<string or null>",
  "deadline": "<ISO8601 datetime or null>",
  "link": "<URL string or null>",
  "confidence": <float 0-1>
}}

Rules:
- type = "application"  → a job application confirmation / acknowledgement email
- type = "oa"           → an online assessment invite (Codility, HackerRank, etc.)
- type = "hirevue"      → a HireVue / one-way video interview invite
- type = "interview"    → a live interview invite (phone / virtual / on-site)
- type = "irrelevant"   → not related to a job application; do not track
- deadline: extract from the email if present, convert to ISO 8601 UTC; null if absent
- link: the direct assessment or meeting URL if present; null otherwise
- confidence: your confidence in the classification (0-1)

Subject: {subject}

Body:
{body}"""


def classify_email(subject: str, body: str) -> dict:
    prompt = _PROMPT_TEMPLATE.format(subject=subject, body=body)
    response = _model.generate_content(prompt)
    text = response.text.strip()

    # Strip accidental markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(text)
