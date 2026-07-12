from datetime import datetime, timezone

from packages.schemas.models import LogEvent
from services.rca_engine.analyzer import analyze_events


def test_primary_error_cluster_becomes_root_cause() -> None:
    events = [
        LogEvent(timestamp=datetime(2026, 7, 11, 9, minute, tzinfo=timezone.utc), service="api", level="ERROR", exception="Timeout: order 123")
        for minute in (1, 2, 3)
    ]
    events.append(LogEvent(timestamp=datetime(2026, 7, 11, 9, 4, tzinfo=timezone.utc), service="worker", level="ERROR", exception="CacheMiss"))

    report = analyze_events(events)

    assert report.affected_services == ["api", "worker"]
    assert "Timeout" in report.suspected_root_cause
    assert len(report.evidence) == 3
