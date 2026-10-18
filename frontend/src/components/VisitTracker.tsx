"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "@/context/AuthContext";

export default function VisitTracker() {
  const { token } = useAuth();
  const hasTracked = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || hasTracked.current) return;

    try {
      // 1. Retrieve or generate persistent visitor ID in localStorage
      let visitorId = localStorage.getItem("instaxoom_visitor_id");
      if (!visitorId) {
        visitorId =
          "vis_" +
          Math.random().toString(36).substring(2, 12) +
          Date.now().toString(36);
        localStorage.setItem("instaxoom_visitor_id", visitorId);
      }

      // 2. Debounce visit reporting per session (30 minutes across browser tabs)
      const sessionKey = "instaxoom_last_visit_ping";
      const lastPing = localStorage.getItem(sessionKey);
      const now = Date.now();
      if (lastPing && now - parseInt(lastPing, 10) < 30 * 60 * 1000) {
        hasTracked.current = true;
        return;
      }

      // 3. Mark as tracked in localStorage and ref
      localStorage.setItem(sessionKey, now.toString());
      hasTracked.current = true;

      // 4. Send non-blocking beacon to backend
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      fetch(`${apiUrl}/api/analytics/visit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          visitor_id: visitorId,
          path: window.location.pathname || "/",
          referrer: document.referrer || undefined,
        }),
      }).catch(() => {
        // Silently swallow network errors so visitor experience is never affected
      });
    } catch {
      // Ignore storage/environment restrictions (e.g. private browsing storage exceptions)
    }
  }, [token]);

  return null;
}
