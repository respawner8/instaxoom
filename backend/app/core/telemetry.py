"""
OpenTelemetry setup for instaXoom.

Wires up all three signals — Traces (Tempo), Metrics (Mimir), Logs (Loki) —
and sends them to Grafana Cloud via OTLP/gRPC.

Call configure_telemetry(app) once at the very start of the FastAPI lifespan,
before init_db() or any other startup work.

When OTEL_ENDPOINT is not set the function is a no-op, so local dev
works without any Grafana credentials.
"""
import logging

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
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
    # Lazily import settings here to avoid circular imports at module load time
    from app.core.config import settings

    if not settings.OTEL_ENDPOINT:
        logger.info(
            "OpenTelemetry disabled: OTEL_ENDPOINT is not set. "
            "Set OTEL_ENDPOINT and OTEL_AUTH_TOKEN in .env to enable."
        )
        return

    auth_headers = {}
    if settings.OTEL_AUTH_TOKEN:
        auth_headers = {"Authorization": f"Basic {settings.OTEL_AUTH_TOKEN}"}

    # ── Shared resource identity ──────────────────────────────────────────────
    # This label block appears on every trace, metric, and log in Grafana so
    # you can filter by service name or environment across all three signal types.
    resource = Resource.create(
        {
            "service.name": "instaxoom-backend",
            "service.version": "1.0.0",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    # ── Traces → Grafana Tempo ────────────────────────────────────────────────
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.OTEL_ENDPOINT,
                headers=auth_headers,
                # insecure=True only for local collector without TLS
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)
    logger.info("OTel TracerProvider configured → %s", settings.OTEL_ENDPOINT)

    # ── Metrics → Grafana Mimir (Prometheus-compatible) ───────────────────────
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=settings.OTEL_ENDPOINT,
            headers=auth_headers,
        ),
        export_interval_millis=30_000,  # push every 30 seconds
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    logger.info("OTel MeterProvider configured (30s export interval)")

    # ── Logs → Grafana Loki ───────────────────────────────────────────────────
    # Bridges Python's standard logging into OTel so every logger.info/error/etc.
    # is forwarded to Loki and automatically correlated with the active trace_id.
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(
                endpoint=settings.OTEL_ENDPOINT,
                headers=auth_headers,
            )
        )
    )
    set_logger_provider(log_provider)

    # Attach to the root logger so all existing logger.xyz() calls are captured
    otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=log_provider)
    logging.getLogger().addHandler(otel_handler)

    # Inject trace_id and span_id into every Python log record's format string
    LoggingInstrumentor().instrument(set_logging_format=True)
    logger.info("OTel LoggerProvider configured → Loki via OTLP")

    # ── Auto-Instrumentation ──────────────────────────────────────────────────

    # FastAPI: creates a root span for every HTTP request with method, route,
    # status code, and duration. Health check and root are excluded to reduce noise.
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="^/$,^/health$",
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    # asyncpg: wraps every database query with a child span showing the SQL
    # statement, table name, and duration. Critical for spotting Neon cold starts
    # and slow credit-check queries.
    AsyncPGInstrumentor().instrument(tracer_provider=tracer_provider)

    # httpx: wraps every outbound HTTP call. This is the single most valuable
    # instrumentation — it captures the Azure AI Foundry call duration as a span,
    # showing exactly how much of /generate time is spent waiting for Azure.
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

    logger.info(
        "OTel auto-instrumentation active: FastAPI, asyncpg, httpx, logging"
    )
