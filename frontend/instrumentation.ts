/**
 * Next.js Instrumentation Hook
 *
 * Next.js automatically loads this file on server startup (both Node.js runtime
 * and Edge runtime). It must be at the root of the project (next to package.json).
 *
 * This wires @vercel/otel to send server-side traces (SSR, API route calls,
 * middleware timing) to Grafana Cloud via the same OTLP endpoint as the backend.
 *
 * Docs: https://nextjs.org/docs/app/building-your-application/optimizing/open-telemetry
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    // Only import on Node.js runtime (not Edge).
    // @vercel/otel handles all provider setup internally.
    const { registerOTel } = await import("@vercel/otel");

    registerOTel({
      serviceName: "instaxoom-frontend",
      // When OTEL_EXPORTER_OTLP_ENDPOINT is set, @vercel/otel automatically
      // picks it up and exports to Grafana Cloud. No extra config needed.
      // The env var is: OTEL_EXPORTER_OTLP_ENDPOINT (set in Vercel project settings)
    });
  }
}
