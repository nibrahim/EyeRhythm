import { useEffect, useState } from "react";
import { connectStatsSocket } from "../api";
import { EMPTY_STATE, type EngineState } from "../types";

export function useEngineState() {
  const [state, setState] = useState<EngineState>(EMPTY_STATE);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    return connectStatsSocket(setState, setConnected);
  }, []);

  return { state, connected };
}
