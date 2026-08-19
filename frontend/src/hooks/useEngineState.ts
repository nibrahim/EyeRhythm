/**
 * Keep the dashboard in sync with the Python engine.
 *
 * Opens a live WebSocket on first render and stores the latest snapshot.
 * `connected` is the green/amber/red light in the title bar.
 */
import { useEffect, useState } from "react";
import { connectStatsSocket } from "../api";
import { EMPTY_STATE, type EngineState } from "../types";

export function useEngineState() {
  const [state, setState] = useState<EngineState>(EMPTY_STATE);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // connectStatsSocket returns a cleanup that closes the socket on unmount.
    return connectStatsSocket(setState, setConnected);
  }, []);

  return { state, connected };
}
