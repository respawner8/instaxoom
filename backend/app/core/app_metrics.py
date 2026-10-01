"""
Application Metrics for instaXoom.

Defines OpenTelemetry / Prometheus custom business and performance metrics:
  - generation_attempts_total (Counter)
  - generation_success_total (Counter)
  - generation_failure_total (Counter)
  - credit_deductions_total (Counter)
  - credit_rejections_total (Counter)
  - revenue_integrity_anomalies_total (Counter — CRITICAL ALERT)
  - user_logins_total (Counter)
  - user_login_failures_total (Counter)
  - azure_generation_duration_seconds (Histogram)
  - azure_queue_wait_seconds (Histogram)
"""
from opentelemetry import metrics

meter = metrics.get_meter("instaxoom.business_metrics", "1.0.0")

# ── Generation Lifecycle Counters ─────────────────────────────────────────────
generation_attempts = meter.create_counter(
    name="generation_attempts_total",
    description="Total image generation requests submitted by users",
    unit="1",
)

generation_success = meter.create_counter(
    name="generation_success_total",
    description="Total image generations that succeeded and delivered an image",
    unit="1",
)

generation_failure = meter.create_counter(
    name="generation_failure_total",
    description="Total image generation requests that failed or threw an error",
    unit="1",
)

# ── Credit & Revenue Integrity Counters ───────────────────────────────────────
credit_deductions = meter.create_counter(
    name="credit_deductions_total",
    description="Total credits successfully deducted from user accounts",
    unit="1",
)

credit_rejections = meter.create_counter(
    name="credit_rejections_total",
    description="Total generation requests rejected due to insufficient credit balance (<1)",
    unit="1",
)

revenue_integrity_anomalies = meter.create_counter(
    name="revenue_integrity_anomalies_total",
    description=(
        "Critical Alert: Discrepancies between image generation and credit balance. "
        "Types: 'gen_success_no_deduct' (free generation) or 'credit_deducted_no_gen' (undelivered image)"
    ),
    unit="1",
)

# ── User Authentication Counters ──────────────────────────────────────────────
user_logins = meter.create_counter(
    name="user_logins_total",
    description="Total successful user logins",
    unit="1",
)

user_login_failures = meter.create_counter(
    name="user_login_failures_total",
    description="Total user authentication failures",
    unit="1",
)

# ── Performance Histograms ───────────────────────────────────────────────────
azure_duration_histogram = meter.create_histogram(
    name="azure_generation_duration_seconds",
    description="Duration of Azure AI Foundry API calls in seconds",
    unit="s",
)

azure_queue_wait_histogram = meter.create_histogram(
    name="azure_queue_wait_seconds",
    description="Time spent waiting in the rate-limit sequential queue before dispatch",
    unit="s",
)
