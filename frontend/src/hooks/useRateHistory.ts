/**
 * Keeps the session rate history warm for Trace for the whole app lifetime.
 *
 * Mount this once near the app root (not only when Trace is visible) so:
 * - sampling starts as soon as the UI boots
 * - history keeps filling while the user is on Atlas / Lumen / Lens / etc.
 * - minimize does not reset the trail (sampler is interval-based)
 */

import { useEffect } from "react";
import {
  ensureRateHistoryRunning,
  setRateHistoryInput,
} from "./rateHistory";

export function useRateHistory(
  continuousBpm: number,
  faceFound: boolean,
): void {
  // Start the 5-minute ring buffer on first mount; never stop for the session.
  useEffect(() => {
    ensureRateHistoryRunning();
  }, []);

  // Push every engine reading into the store (face flag kept for API stability).
  useEffect(() => {
    setRateHistoryInput(continuousBpm, faceFound);
  }, [continuousBpm, faceFound]);
}
