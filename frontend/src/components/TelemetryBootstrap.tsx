"use client";

/**
 * TelemetryBootstrap
 *
 * A zero-render client component that runs once on mount to register:
 *   1. Web Vitals observers (LCP, FCP, long animation frames)
 *   2. Global error handlers (uncaught exceptions + unhandled rejections)
 *
 * Renders nothing (returns null). Placed at the top of RootLayout so it
 * activates on every page before any other component mounts.
 */
import { useEffect } from "react";
import { trackWebVitals, registerErrorTracking } from "@/lib/telemetry";

export default function TelemetryBootstrap() {
  useEffect(() => {
    trackWebVitals();
    registerErrorTracking();
  }, []); // empty deps — run once on first mount only

  return null;
}
