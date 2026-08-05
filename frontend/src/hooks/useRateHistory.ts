/**
 * Keeps the session rate history warm for Trace, regardless of avatar view.
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
  useEffect(() => {
    ensureRateHistoryRunning();
  }, []);

  useEffect(() => {
    setRateHistoryInput(continuousBpm, faceFound);
  }, [continuousBpm, faceFound]);
}
