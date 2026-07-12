import json

from packages.schemas.models import Evidence, RCAReport
from services.agent import llm_explainer


def test_enrich_report_requests_structured_output(monkeypatch) -> None:
    request = {}

    class FakeResponses:
        def create(self, **kwargs):
            request.update(kwargs)
            return type(
                "Response",
                (),
                {
                    "output_text": json.dumps(
                        {
                            "explanation": "The checkout errors share a gateway timeout signature.",
                            "next_steps": ["Check the payment gateway status."],
                        }
                    )
                },
            )()

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", lambda **_: FakeClient())
    report = RCAReport(
        incident_summary="Checkout failures",
        suspected_root_cause="GatewayTimeout",
        confidence=75,
        affected_services=["checkout-api"],
        evidence=[
            Evidence(
                timestamp="2026-07-11T09:00:03Z",
                service="checkout-api",
                message="Payment gateway request failed",
                exception="GatewayTimeout",
            )
        ],
        recommended_next_steps=["Inspect gateway latency."],
    )

    result = llm_explainer.enrich_report(report)

    assert result.ai_explanation
    assert request["text"]["format"] == {
        "type": "json_schema",
        "name": "rca_explanation",
        "schema": llm_explainer.EXPLANATION_SCHEMA,
        "strict": True,
    }


def test_get_provider_defaults_to_openai(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert isinstance(llm_explainer.get_provider(), llm_explainer.OpenAIProvider)


def test_get_provider_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    try:
        llm_explainer.get_provider()
    except llm_explainer.LLMConfigurationError as exc:
        assert "Unsupported LLM_PROVIDER" in str(exc)
    else:
        raise AssertionError("Expected an unsupported provider error")
