/**
 * Browser-side telemetry for instaXoom.
 *
 * Sends structured events to our own backend telemetry endpoint which forwards
 * them to Grafana Loki as structured logs. This is intentionally lightweight —
 * the full OTel browser SDK is ~200KB and not suitable for a production web app.
 *
 * What this captures:
 *   - Google Sign-In latency (credential received → JWT stored)
 *   - Image generation: time from submit → SSE first byte → image rendered
 *   - Client-side errors (uncaught exceptions, rejected promises)
 *   - Page load performance (LCP, FCP from PerformanceObserver)
 *
 * Server-side (SSR + fetch calls to FastAPI) is handled by @vercel/otel via
 * instrumentation.ts and the trace context propagated automatically.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Unique session ID generated once per browser tab. */
const SESSION_ID =
  typeof crypto !== "undefined"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

export interface TelemetryEvent {
  event: string;
  session_id: string;
  timestamp: string;
  duration_ms?: number;
  [key: string]: unknown;
}

/**
 * Send a telemetry event to the backend /api/telemetry/event endpoint.
 * Fire-and-forget — never throws, never blocks UI.
 */
export function trackEvent(
  eventName: string,
  attributes: Record<string, unknown> = {}
): void {
  if (typeof window === "undefined") return; // SSR guard

  const payload: TelemetryEvent = {
    event: eventName,
    session_id: SESSION_ID,
    timestamp: new Date().toISOString(),
    user_agent: navigator.userAgent,
    ...attributes,
  };

  // Use sendBeacon for events on page unload; fall back to fetch for normal events
  const url = `${API_URL}/api/telemetry/event`;
  const body = JSON.stringify(payload);

  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
    } else {
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => {}); // intentionally swallow errors
    }
  } catch {
    // Never surface telemetry errors to the user
  }
}

/**
 * Measure an async operation and emit a telemetry event with its duration.
 *
 * Usage:
 *   const user = await measure("auth.google_login", async () => {
 *     return await loginWithGoogle(credential);
 *   }, { user_email: email });
 */
export async function measure<T>(
  eventName: string,
  fn: () => Promise<T>,
  attributes: Record<string, unknown> = {}
): Promise<T> {
  const start = performance.now();
  let status = "success";
  let errorMessage: string | undefined;

  try {
    const result = await fn();
    return result;
  } catch (err) {
    status = "error";
    errorMessage = err instanceof Error ? err.message : String(err);
    throw err;
  } finally {
    const duration_ms = Math.round(performance.now() - start);
    trackEvent(eventName, {
      duration_ms,
      status,
      ...(errorMessage ? { error: errorMessage } : {}),
      ...attributes,
    });
  }
}

/**
 * Track Web Vitals — LCP, FCP, CLS, INP via PerformanceObserver.
 * Call once from a client component (e.g. layout.tsx).
 */
export function trackWebVitals(): void {
  if (typeof window === "undefined" || !("PerformanceObserver" in window))
    return;

  // Largest Contentful Paint
  try {
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1] as PerformanceEntry & {
        startTime: number;
      };
      if (last) {
        trackEvent("web_vital.lcp", {
          value_ms: Math.round(last.startTime),
          rating: last.startTime < 2500 ? "good" : last.startTime < 4000 ? "needs_improvement" : "poor",
        });
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch {}

  // First Contentful Paint
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.name === "first-contentful-paint") {
          trackEvent("web_vital.fcp", {
            value_ms: Math.round(entry.startTime),
            rating: entry.startTime < 1800 ? "good" : entry.startTime < 3000 ? "needs_improvement" : "poor",
          });
        }
      }
    }).observe({ type: "paint", buffered: true });
  } catch {}

  // Long animation frames (INP proxy)
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const e = entry as PerformanceEntry & { duration: number };
        if (e.duration > 50) {
          trackEvent("web_vital.long_animation_frame", {
            duration_ms: Math.round(e.duration),
          });
        }
      }
    }).observe({ type: "long-animation-frame", buffered: true });
  } catch {}
}

/**
 * Register global error handlers to capture uncaught exceptions and
 * unhandled promise rejections. Call once in root layout.
 */
export function registerErrorTracking(): void {
  if (typeof window === "undefined") return;

  window.addEventListener("error", (event) => {
    trackEvent("client.error", {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      stack: event.error?.stack?.slice(0, 500),
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    trackEvent("client.unhandled_rejection", {
      message: reason instanceof Error ? reason.message : String(reason),
      stack: reason instanceof Error ? reason.stack?.slice(0, 500) : undefined,
    });
  });
}
