/** Live engine snapshot (mirrors app.engine.EngineSnapshot). */
export interface EngineState {
  continuous_bpm: number;
  average_bpm: number;
  /** Ocular Rhythm Index — 70 % rate + 30 % regularity (0–100). */
  ocular_rhythm_index: number | null;
  /** True when both rate and regularity contribute to ORI. */
  ocular_rhythm_full: boolean;
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
  /** Degrees between face/eye axis and camera axis; null when no face. */
  face_angle_deg: number | null;
  face_yaw_deg: number | null;
  face_pitch_deg: number | null;
  /** "straight" | "left" | "right-top" | … ; null when no face. */
  face_direction: string | null;
  /** Looking down (bottom / left-bottom / right-bottom) with look-angle ≥ 20°. */
  off_screen: boolean;

  beep: boolean;
  alert: boolean;
  ontop: boolean;
  practice: boolean;
  /** "off" | "countdown" | "active" | "summary" */
  practice_phase: string;
  /** Seconds left in the pre-start countdown. */
  practice_countdown_s: number;
  /** Total countdown length (for progress UI). */
  practice_countdown_total_s: number;
  /** Seconds left in the active beeping practice (0 when not active). */
  practice_remaining_s: number;
  /** Beep / ball travel interval in seconds. */
  practice_interval_s: number;
  /** Wall-clock epoch when active practice began (0 if idle). */
  practice_active_started_at: number;
  /** Seconds left on the post-practice results screen. */
  practice_summary_s: number;
  /** Frozen practice-session blink count. */
  practice_result_blinks: number;
  /** Frozen practice-session blink rate (/min). */
  practice_result_bpm: number;
  /** Frozen practice-session regularity (0–100), or null if not ready. */
  practice_result_regularity: number | null;
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
  ocular_rhythm_index: null,
  ocular_rhythm_full: false,
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
  face_angle_deg: null,
  face_yaw_deg: null,
  face_pitch_deg: null,
  face_direction: null,
  off_screen: false,
  beep: false,
  alert: false,
  ontop: false,
  practice: false,
  practice_phase: "off",
  practice_countdown_s: 0,
  practice_countdown_total_s: 20,
  practice_remaining_s: 0,
  practice_interval_s: 3,
  practice_active_started_at: 0,
  practice_summary_s: 0,
  practice_result_blinks: 0,
  practice_result_bpm: 0,
  practice_result_regularity: null,
  last_blink_at: 0,
  last_alert_beep_at: 0,
  future_a: null,
  future_b: null,
  running: false,
  timestamp: 0,
};

export type ToggleName = "beep" | "alert" | "ontop" | "practice";
