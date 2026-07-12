# RCA Copilot

A small, evidence-first root-cause-analysis service for application logs.

The MVP accepts structured JSON logs, detects error clusters, and uses an LLM
to explain the evidence-backed result. OpenAI is the default provider.

## Quick start

```bash
cd rca-copilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key" # Default provider
uvicorn apps.api.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to use the interactive API documentation.

Or start it in Docker:

```bash
docker compose up --build
```

## Analyze sample logs

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  --data @tests/fixtures/checkout_incident.json
```

Each event should contain `timestamp`, `service`, and `level`. Error events
can include `message`, `exception`, `trace_id`, and `deployment_version`.

## Current MVP behavior

- Filters `ERROR`, `FATAL`, and `CRITICAL` events.
- Groups events by service and normalized exception/message signature.
- Ranks clusters by event count and recency.
- Sends only the resulting report and selected evidence to the LLM.
- Returns the suspected root cause, concrete evidence, and AI explanation.

## LLM providers

Set `LLM_PROVIDER` to choose a provider. If it is not set, the service uses
OpenAI.

| Provider | Required setting | Optional model setting | Default model |
| --- | --- | --- | --- |
| OpenAI (default) | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-5-mini` |
| Groq | `GROQ_API_KEY` | `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL` | `gemini-2.5-flash` |
| Ollama | None | `OLLAMA_MODEL` | `llama3.2` |

Examples:

```bash
# Free-tier hosted Groq account
export LLM_PROVIDER=groq
export GROQ_API_KEY="your-groq-key"

# Gemini API
export LLM_PROVIDER=gemini
export GEMINI_API_KEY="your-gemini-key"

# Local Ollama (first run: ollama pull llama3.2)
export LLM_PROVIDER=ollama
```

Keep real keys in your shell, secret manager, or an untracked `.env` file.

The next increment is to add OpenTelemetry metrics/traces and connector
adapters, then have an AI model explain only the retrieved evidence.
