/** Live engine snapshot (mirrors app.engine.EngineSnapshot). */
export interface EngineState {
  continuous_bpm: number;
  average_bpm: number;
  screen_time: string;
  screen_time_seconds: number;
  fps: number;
  regularity: number | null;
  regularity_ready: boolean;
  /** Number of inter-blink gaps collected (for warm-up UI). */
  regularity_gaps: number;

  blinks_today: number;
  session_blinks: number;
  eyes_closed: boolean;
  face_found: boolean;
  blink_score: number;

  camera_ok: boolean;
  camera_message: string;
  is_frontal: boolean;
  has_glasses: boolean;
  low_light: boolean;

  beep: boolean;
  alert: boolean;
  ontop: boolean;
  practice: boolean;
  /** "off" | "countdown" | "active" */
  practice_phase: string;
  /** Seconds left in the 10s pre-start countdown. */
  practice_countdown_s: number;
  /** Seconds left in the active beeping practice (0 when not active). */
  practice_remaining_s: number;
  /** Wall-clock: last counted blink (Beep/Practice orange pulse). */
  last_blink_at: number;
  /** Wall-clock: last low-rate alert beep (Alert red pulse). */
  last_alert_beep_at: number;

  future_a: null;
  future_b: null;

  running: boolean;
  timestamp: number;
}

export const EMPTY_STATE: EngineState = {
  continuous_bpm: 0,
  average_bpm: 0,
  screen_time: "0m",
  screen_time_seconds: 0,
  fps: 0,
  regularity: null,
  regularity_ready: false,
  regularity_gaps: 0,
  blinks_today: 0,
  session_blinks: 0,
  eyes_closed: false,
  face_found: false,
  blink_score: 0,
  camera_ok: false,
  camera_message: "connecting…",
  is_frontal: true,
  has_glasses: false,
  low_light: false,
  beep: false,
  alert: false,
  ontop: false,
  practice: false,
  practice_phase: "off",
  practice_countdown_s: 0,
  practice_remaining_s: 0,
  last_blink_at: 0,
  last_alert_beep_at: 0,
  future_a: null,
  future_b: null,
  running: false,
  timestamp: 0,
};

export type ToggleName = "beep" | "alert" | "ontop" | "practice";
