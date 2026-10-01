"""
OpenTelemetry setup for instaXoom.

Wires up all three signals — Traces (Tempo), Metrics (Mimir), Logs (Loki) —
and sends them to Grafana Cloud via OTLP/gRPC.

The OTel SDK automatically reads these standard env vars (set them in .env):
  OTEL_EXPORTER_OTLP_ENDPOINT  — Grafana OTLP gateway URL
  OTEL_EXPORTER_OTLP_HEADERS   — "Authorization=Basic <base64token>"

Both are provided verbatim by Grafana Cloud's OTel setup page.
When OTEL_EXPORTER_OTLP_ENDPOINT is not set, this is a complete no-op —
the app starts normally with no telemetry (safe for local dev).

Call configure_telemetry(app) once at the very start of the FastAPI lifespan,
before init_db() or any other startup work.
"""
import logging

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def configure_telemetry(app) -> None:
    """
    Initialise OpenTelemetry for the FastAPI application.

    The OTel SDK reads OTEL_EXPORTER_OTLP_ENDPOINT and
    OTEL_EXPORTER_OTLP_HEADERS automatically from the environment —
    no need to pass them manually to each exporter.

    Registers:
      - TracerProvider  → Grafana Tempo  (distributed traces)
      - MeterProvider   → Grafana Mimir  (Prometheus-compatible metrics)
      - LoggerProvider  → Grafana Loki   (structured logs, correlated to traces)

    Auto-instruments:
      - FastAPI request spans (every HTTP route)
      - asyncpg queries (every SQL statement as a child span)
      - httpx outbound calls (Azure AI Foundry API calls)
      - Python standard logging (injects trace_id / span_id into every log line)
    """
    import os
    from app.core.config import settings

    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        logger.info(
            "OpenTelemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT is not set. "
            "Add it to .env to enable (see Grafana Cloud → OpenTelemetry setup page)."
        )
        return

    # Critical fix: Pydantic loads .env into Settings attributes, but does NOT
    # populate os.environ. The OpenTelemetry SDK exporters inspect os.environ.
    # Without this, OTLPSpanExporter falls back to http://localhost:4318/v1/traces!
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    if settings.OTEL_EXPORTER_OTLP_HEADERS:
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = settings.OTEL_EXPORTER_OTLP_HEADERS

    # ── Shared resource identity ──────────────────────────────────────────────
    # Appears on every trace, metric, and log in Grafana —
    # use it to filter by service name or environment.
    resource = Resource.create(
        {
            "service.name": "instaxoom-backend",
            "service.version": "1.0.0",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    # ── Traces → Grafana Tempo ────────────────────────────────────────────────
    # OTLPSpanExporter reads OTEL_EXPORTER_OTLP_ENDPOINT & HEADERS from os.environ
    span_exporter = OTLPSpanExporter()
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(span_exporter)
    )
    trace.set_tracer_provider(tracer_provider)
    print(f"[OTel] ✓ TracerProvider target → {span_exporter._endpoint}")

    # ── Metrics → Grafana Mimir (Prometheus-compatible) ───────────────────────
    metric_exporter = OTLPMetricExporter()
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=30_000,
            )
        ],
    )
    metrics.set_meter_provider(meter_provider)
    print(f"[OTel] ✓ MeterProvider target → {metric_exporter._endpoint} (30s interval)")

    # ── Logs → Grafana Loki ───────────────────────────────────────────────────
    # Bridges Python's standard logging into OTel so every logger.info/error
    # is forwarded to Loki and automatically correlated with the active trace_id.
    log_exporter = OTLPLogExporter()
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )
    set_logger_provider(log_provider)

    # Attach OTel handler to root logger — captures all existing logger.xyz() calls
    # Set root logger level to INFO so info-level application logs are captured (default is WARNING).
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(isinstance(h, LoggingHandler) for h in root_logger.handlers):
        otel_handler = LoggingHandler(level=logging.INFO, logger_provider=log_provider)
        root_logger.addHandler(otel_handler)

    # Ensure uvicorn access logs ("GET /api/... 200 OK") propagate to root logger so they reach Loki
    for u_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(u_name).propagate = True

    # Injects trace_id and span_id into every Python log record format string
    LoggingInstrumentor().instrument(set_logging_format=True)
    print(f"[OTel] ✓ LoggerProvider target → {log_exporter._endpoint}")

    # ── Auto-Instrumentation ──────────────────────────────────────────────────

    # FastAPI: root span per HTTP request — method, route, status, duration.
    # Exclude only root '/' to reduce noise, allow '/health' so testing endpoints work.
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="^/$",
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    # asyncpg: child span per DB query showing SQL statement and duration.
    # Critical for spotting Neon cold starts and slow credit-check queries.
    AsyncPGInstrumentor().instrument(tracer_provider=tracer_provider)

    # httpx: child span per outbound HTTP call.
    # This captures Azure AI Foundry call duration — showing exactly
    # how much of /generate time is spent waiting for the model.
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

    print("[OTel] ✓ Auto-instrumentation active: FastAPI, asyncpg, httpx, logging")

    # ── Startup verification span ──────────────────────────────────────────────
    # Emits an initial span so Grafana Cloud receives live data on boot.
    # Exported asynchronously by BatchSpanProcessor without blocking startup.
    try:
        tracer = trace.get_tracer("instaxoom.startup", tracer_provider=tracer_provider)
        with tracer.start_as_current_span("app.startup") as span:
            span.set_attribute("service.name", "instaxoom-backend")
            span.set_attribute("service.status", "ready")
            span.set_attribute("environment", settings.ENVIRONMENT)
    except Exception as e:
        logger.warning(f"[OTel] Failed to record initial startup trace: {e}")
