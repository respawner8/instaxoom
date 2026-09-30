"""
Telemetry event receiver for browser-side events.

The frontend sends structured JSON events (Google Sign-In latency, Web Vitals,
generation timing, client errors) to this endpoint. The backend logs them as
structured log lines, which are picked up by the OTel logging bridge and
forwarded to Grafana Loki — correlated with the same service.name "instaxoom-backend".

This avoids shipping the heavy OTel browser SDK (~200KB) to the client while
still getting structured observability data into Grafana.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])
logger = logging.getLogger("instaxoom.frontend_events")


class BrowserEvent(BaseModel):
    """
    Structured event emitted by the browser-side telemetry utility.
    All fields beyond `event` and `session_id` are optional — the client
    sends whatever attributes are relevant to that event type.
    """
    event: str
    session_id: str
    timestamp: Optional[str] = None
    duration_ms: Optional[float] = None
    status: Optional[str] = None
    user_agent: Optional[str] = None
    # Catch-all for event-specific attributes (theme_id, credits, error, etc.)
    model_config = {"extra": "allow"}


@router.post("/event", status_code=204)
async def receive_browser_event(
    payload: BrowserEvent,
    request: Request,
) -> None:
    """
    Receives a single telemetry event from the browser.
    Logs it as a structured record so the OTel logging bridge picks it up
    and forwards it to Grafana Loki.

    Returns 204 No Content — the browser never reads the response body.
    """
    # Build a flat dict of all fields (including extra/dynamic ones from model)
    event_data: dict[str, Any] = payload.model_dump(exclude_none=True)

    # Add server-side context the browser can't know
    event_data["source"] = "browser"
    event_data["client_ip"] = _get_client_ip(request)
    event_data["received_at"] = datetime.now(timezone.utc).isoformat()

    # Emit as a structured log line. The OTel logging bridge injects
    # trace_id and span_id automatically if there's an active server span.
    logger.info(
        "browser_event: %s",
        payload.event,
        extra={"browser_telemetry": event_data},
    )


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
