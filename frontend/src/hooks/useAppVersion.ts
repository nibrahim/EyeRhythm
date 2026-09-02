/**
 * Product version from GET /api/health (app/version.py).
 * Empty string until the local server answers.
 */
import { useEffect, useState } from "react";
import { fetchHealth } from "../api";

export function useAppVersion(): string {
  const [version, setVersion] = useState("");

  useEffect(() => {
    let cancelled = false;
    void fetchHealth()
      .then((health) => {
        const value = String(health.version ?? "").trim();
        if (!cancelled && value) setVersion(value);
      })
      .catch(() => {
        /* About / splash stay version-less if the server is still starting */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return version;
}
