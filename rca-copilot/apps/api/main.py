import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from packages.schemas.models import AnalyzeRequest, RCAReport
from services.agent.llm_explainer import LLMConfigurationError, enrich_report
from services.rca_engine.analyzer import analyze_events

# Load local development settings without overwriting variables supplied by the
# shell, container, or deployment platform.
load_dotenv()

app = FastAPI(
    title="RCA Copilot",
    version="0.1.0",
    description="Evidence-first root-cause analysis for structured logs.",
)
logger = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=RCAReport)
def analyze(request: AnalyzeRequest) -> RCAReport:
    if not request.events:
        raise HTTPException(status_code=400, detail="Provide at least one log event.")
    report = analyze_events(request.events)
    try:
        return enrich_report(report)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("LLM analysis failed")
        raise HTTPException(
            status_code=502, detail="LLM analysis could not be completed. Check the API key and model configuration."
        ) from exc
