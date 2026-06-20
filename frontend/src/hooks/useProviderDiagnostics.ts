import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { diagnosticsApi, type ProviderCheck } from "@/lib/api";

/**
 * Fetches a live probe of every external provider (Gemini, Cala, PixVerse,
 * Devin) and logs the result of each external API call to the browser console,
 * so it's easy to tell whether the API keys from the `.env` actually work.
 */
export function useProviderDiagnostics(enabled = true) {
  const query = useQuery({
    queryKey: ["diagnostics", "providers"],
    queryFn: async () => (await diagnosticsApi.providers()).data.providers,
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    if (!query.data) return;
    logProviderChecks(query.data);
  }, [query.data]);

  useEffect(() => {
    if (query.error) {
      // eslint-disable-next-line no-console
      console.error("[Coursive] provider diagnostics request failed", query.error);
    }
  }, [query.error]);

  return query;
}

function logProviderChecks(checks: ProviderCheck[]) {
  /* eslint-disable no-console */
  console.groupCollapsed(
    "%c[Coursive] External API key check",
    "font-weight:bold;color:#6366f1",
  );
  for (const c of checks) {
    const latency = c.latency_ms != null ? ` ${c.latency_ms}ms` : "";
    const httpStatus = c.status != null ? ` HTTP ${c.status}` : "";
    if (!c.configured) {
      console.log(
        `%c○ ${c.provider}%c not configured — ${c.label}`,
        "color:#9ca3af;font-weight:bold",
        "color:#9ca3af",
      );
    } else if (c.ok) {
      console.log(
        `%c✓ ${c.provider}%c OK${httpStatus}${latency} — ${c.detail}`,
        "color:#16a34a;font-weight:bold",
        "color:inherit",
      );
    } else {
      console.warn(
        `%c✗ ${c.provider}%c FAILED${httpStatus}${latency} — ${c.detail}`,
        "color:#dc2626;font-weight:bold",
        "color:inherit",
      );
    }
  }
  console.table(
    checks.map((c) => ({
      provider: c.provider,
      configured: c.configured,
      ok: c.ok,
      status: c.status,
      latency_ms: c.latency_ms,
      detail: c.detail,
    })),
  );
  console.groupEnd();
  /* eslint-enable no-console */
}
