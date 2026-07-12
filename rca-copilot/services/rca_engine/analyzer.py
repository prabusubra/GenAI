import re
from collections import defaultdict

from packages.schemas.models import Evidence, LogEvent, RCAReport

ERROR_LEVELS = {"ERROR", "FATAL", "CRITICAL"}


def _signature(event: LogEvent) -> str:
    """Create a stable grouping key while removing volatile numeric IDs."""
    source = event.exception or event.message or "Unclassified error"
    normalized = re.sub(r"\b[0-9a-f]{8,}\b|\b\d+\b", "<id>", source.lower())
    return " ".join(normalized.split())


def analyze_events(events: list[LogEvent]) -> RCAReport:
    error_events = [event for event in events if event.level.upper() in ERROR_LEVELS]
    if not error_events:
        return RCAReport(
            incident_summary="No error-level events found in the supplied logs.",
            suspected_root_cause="No root cause can be inferred without error evidence.",
            confidence=0,
            affected_services=[],
            evidence=[],
            recommended_next_steps=["Supply a wider time range or include ERROR/FATAL log events."],
        )

    clusters: dict[tuple[str, str], list[LogEvent]] = defaultdict(list)
    for event in error_events:
        clusters[(event.service, _signature(event))].append(event)

    def score(cluster: list[LogEvent]) -> tuple[int, float]:
        newest = max(event.timestamp for event in cluster).timestamp()
        return len(cluster), newest

    (service, signature), primary = max(clusters.items(), key=lambda item: score(item[1]))
    primary = sorted(primary, key=lambda event: event.timestamp, reverse=True)
    total_errors = len(error_events)
    ratio = len(primary) / total_errors
    confidence = min(95, max(35, round(45 + ratio * 50)))
    representative = primary[0]
    label = representative.exception or representative.message or signature

    evidence = [
        Evidence(
            timestamp=event.timestamp,
            service=event.service,
            message=event.message,
            exception=event.exception,
            trace_id=event.trace_id,
        )
        for event in primary[:5]
    ]
    affected_services = sorted({event.service for event in error_events})
    deployment_hint = (
        f" Check deployment {representative.deployment_version}."
        if representative.deployment_version
        else ""
    )

    return RCAReport(
        incident_summary=(
            f"Detected {total_errors} error events across {len(affected_services)} service(s). "
            f"The largest cluster has {len(primary)} event(s) in {service}."
        ),
        suspected_root_cause=f"Likely failure cluster in {service}: {label}",
        confidence=confidence,
        affected_services=affected_services,
        evidence=evidence,
        recommended_next_steps=[
            f"Inspect the {service} logs and stack trace for this signature.",
            "Use the trace IDs in the evidence to follow the failing request across services.",
            f"Compare the incident window with recent configuration or code changes.{deployment_hint}",
        ],
    )
