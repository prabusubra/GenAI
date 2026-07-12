"""Provider-agnostic LLM explanation layer for deterministic RCA reports."""

import json
import os
from typing import Protocol
from urllib.parse import quote
from urllib.request import Request, urlopen

from packages.schemas.models import RCAReport

SYSTEM_PROMPT = """You are RCA Copilot, an SRE incident-analysis assistant.
Explain the supplied deterministic analysis using only the included evidence.
Do not claim a root cause is confirmed. Do not invent incidents, services,
deployments, error counts, or remediation actions.
Return only a JSON object with `explanation` and `next_steps` keys."""

EXPLANATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "explanation": {"type": "string"},
        "next_steps": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
    },
    "required": ["explanation", "next_steps"],
}


class LLMConfigurationError(RuntimeError):
    """Raised when the selected provider is missing required configuration."""


class ExplanationProvider(Protocol):
    """Strategy interface implemented by each LLM provider."""

    def generate(self, payload: dict[str, object]) -> str:
        """Return the JSON explanation generated for the supplied RCA payload."""


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise LLMConfigurationError(f"{name} is not configured.")
    return value


class OpenAIProvider:
    """OpenAI Responses API strategy (the default provider)."""

    def generate(self, payload: dict[str, object]) -> str:
        from openai import OpenAI

        response = OpenAI(api_key=_require_env("OPENAI_API_KEY")).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            instructions=SYSTEM_PROMPT,
            input=json.dumps(payload),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "rca_explanation",
                    "schema": EXPLANATION_SCHEMA,
                    "strict": True,
                }
            },
        )
        return response.output_text


class GroqProvider:
    """Groq Chat Completions strategy using its OpenAI-compatible API."""

    def generate(self, payload: dict[str, object]) -> str:
        from openai import OpenAI

        client = OpenAI(
            api_key=_require_env("GROQ_API_KEY"),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned an empty explanation.")
        return content


class GeminiProvider:
    """Gemini Generate Content REST API strategy."""

    def generate(self, payload: dict[str, object]) -> str:
        api_key = _require_env("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        request_body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": json.dumps(payload)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": EXPLANATION_SCHEMA,
            },
        }
        request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(model, safe='')}:generateContent?key={quote(api_key, safe='')}",
            data=json.dumps(request_body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            response_body = json.loads(response.read().decode())
        try:
            return response_body["candidates"][0]["content"]["parts"][0]["text"]
        except (IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("Gemini returned no explanation text.") from exc


class OllamaProvider:
    """Local Ollama chat API strategy; no API key is required."""

    def generate(self, payload: dict[str, object]) -> str:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        request_body = {
            "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            "format": "json",
            "stream": False,
        }
        request = Request(
            f"{base_url}/api/chat",
            data=json.dumps(request_body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            response_body = json.loads(response.read().decode())
        try:
            return response_body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Ollama returned no explanation text.") from exc


def get_provider() -> ExplanationProvider:
    """Select an LLM strategy from ``LLM_PROVIDER`` (OpenAI by default)."""
    providers: dict[str, type[ExplanationProvider]] = {
        "openai": OpenAIProvider,
        "groq": GroqProvider,
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
    }
    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    provider_type = providers.get(provider_name)
    if provider_type is None:
        supported = ", ".join(sorted(providers))
        raise LLMConfigurationError(
            f"Unsupported LLM_PROVIDER '{provider_name}'. Choose one of: {supported}."
        )
    return provider_type()


def _parse_explanation(output: str) -> tuple[str, list[str]]:
    try:
        explanation = json.loads(output)
        text = explanation["explanation"].strip()
        next_steps = explanation.get("next_steps", [])
        if not text or not isinstance(next_steps, list) or not all(
            isinstance(step, str) for step in next_steps
        ):
            raise ValueError("Response does not match the expected JSON shape.")
    except (json.JSONDecodeError, KeyError, AttributeError, ValueError) as exc:
        raise RuntimeError("The LLM returned an invalid RCA explanation.") from exc
    return text, next_steps[:3]


def enrich_report(report: RCAReport) -> RCAReport:
    """Use the selected LLM strategy to create an operator-friendly explanation."""
    payload: dict[str, object] = {
        "deterministic_report": report.model_dump(
            mode="json", exclude={"ai_explanation", "ai_recommended_next_steps"}
        ),
        "allowed_evidence": [item.model_dump(mode="json") for item in report.evidence],
    }
    text, next_steps = _parse_explanation(get_provider().generate(payload))
    return report.model_copy(
        update={"ai_explanation": text, "ai_recommended_next_steps": next_steps}
    )
