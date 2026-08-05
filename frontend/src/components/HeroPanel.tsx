import { useEffect, useState } from "react";
import { startPreviewPolling } from "../api";
import { useRateHistory } from "../hooks/useRateHistory";
import type { EngineState } from "../types";
import { eyesLabel, rateTone } from "../utils/format";
import { Avatar, AvatarPicker, type AvatarId } from "./Avatar";
import { RateGraph } from "./RateGraph";

interface Props {
  state: EngineState;
  avatarId: AvatarId;
  onAvatarChange: (id: AvatarId) => void;
}

/**
 * Hero: single avatar stage (fixed height for every mode).
 * - Eyes status pill: centered on the top of the head (hidden for Trace)
 * - Blinks today: top-right (avatar modes only — hidden in Trace)
 * - Picker: Atlas / Lumen / Vesper / Lens / Trace
 * - Rate history always records so Trace keeps the last 5 minutes
 */
export function HeroPanel({ state, avatarId, onAvatarChange }: Props) {
  const tone = rateTone(state.continuous_bpm, state.face_found);
  const label = eyesLabel(state.face_found, state.eyes_closed);
  const isLens = avatarId === "lens";
  const isGraph = avatarId === "graph";
  const [frameUrl, setFrameUrl] = useState<string | null>(null);

  // Always sample — history survives avatar switches.
  useRateHistory(state.continuous_bpm, state.face_found);

  useEffect(() => {
    if (!isLens) {
      setFrameUrl(null);
      return;
    }
    return startPreviewPolling(setFrameUrl);
  }, [isLens]);

  const heroMod =
    (isLens ? " hero--lens" : "") + (isGraph ? " hero--graph" : "");

  return (
    <section className={`hero${heroMod}`}>
      {!isGraph && (
        <div className="hero__stat-chip">
          <span className="hero__stat-value">{state.blinks_today}</span>
          <span className="hero__stat-label">blinks today</span>
        </div>
      )}

      <div className="hero__stage-wrap">
        <div className="hero__avatar-stage">
          {isGraph ? (
            <RateGraph
              faceFound={state.face_found}
              lastBlinkAt={state.last_blink_at}
            />
          ) : (
            <Avatar
              id={avatarId}
              eyesClosed={state.eyes_closed}
              faceFound={state.face_found}
              blinkScore={state.blink_score}
              cameraFrameUrl={frameUrl}
              cameraOk={state.camera_ok}
              cameraMessage={state.camera_message}
            />
          )}
          {!isGraph && (
            <div className={`hero__status-pill pill tone-${tone}`}>
              <span className="pill__dot" />
              {label}
            </div>
          )}
        </div>
      </div>

      <AvatarPicker value={avatarId} onChange={onAvatarChange} />
    </section>
  );
}
