import { useCallback, useEffect, useState } from "react";
import { fetchPreferences, savePreferences, setToggle } from "./api";
import { whenBridgeReady } from "./bridge";
import { type AvatarId } from "./components/Avatar";
import { ControlsBar } from "./components/ControlsBar";
import { HeroPanel } from "./components/HeroPanel";
import { Logo } from "./components/Logo";
import { MetricCard } from "./components/MetricCard";
import { InfoQuoteCard } from "./components/InfoQuoteCard";
import { PracticeScreen } from "./components/PracticeScreen";
import { useEngineState } from "./hooks/useEngineState";
import { useRateHistory } from "./hooks/useRateHistory";
import { formatBpm, regularityTone, rateTone } from "./utils/format";

const AVATARS: AvatarId[] = ["atlas", "lumen", "vesper", "lens", "graph"];

function asAvatarId(v: unknown): AvatarId {
  if (typeof v === "string" && (AVATARS as string[]).includes(v)) {
    return v as AvatarId;
  }
  return "atlas";
}

export default function App() {
  const { state, connected } = useEngineState();
  const [avatarId, setAvatarId] = useState<AvatarId>("atlas");
  const [prefsReady, setPrefsReady] = useState(false);

  // Session-wide Trace history: starts at boot, survives avatar switches + minimize.
  useRateHistory(state.continuous_bpm, state.face_found);

  useEffect(() => {
    void whenBridgeReady();
  }, []);

  // Restore last avatar (and confirm prefs API is up).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const prefs = await fetchPreferences();
        if (!cancelled) {
          setAvatarId(asAvatarId(prefs.avatar));
        }
      } catch {
        /* keep default */
      } finally {
        if (!cancelled) setPrefsReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persistAvatar = useCallback((id: AvatarId) => {
    setAvatarId(id);
    void savePreferences({ avatar: id }).catch(() => {
      /* offline / restarting */
    });
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      const k = e.key.toLowerCase();
      if (k === "b") void setToggle("beep");
      else if (k === "a") void setToggle("alert");
      else if (k === "t") void setToggle("ontop");
      else if (k === "p") void setToggle("practice");
      else if (k === "c") {
        persistAvatar(avatarId === "lens" ? "atlas" : "lens");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [avatarId, persistAvatar]);

  const bpmTone = rateTone(state.continuous_bpm, state.face_found);
  const avgTone = rateTone(state.average_bpm, state.screen_time_seconds > 30);
  const regTone = regularityTone(state.regularity);

  const regValue =
    state.regularity_ready && state.regularity !== null
      ? Math.round(state.regularity)
      : "—";
  const regSub = state.regularity_ready
    ? "inter-blink rhythm"
    : state.regularity_gaps > 0
      ? `warming up · ${state.regularity_gaps}/2 gaps`
      : "need a few blinks";

  return (
    <div className="app-shell" data-prefs-ready={prefsReady ? "1" : "0"}>
      <header className="topbar">
        <div className="topbar__brand">
          <Logo size={30} />
          <div>
            <div className="topbar__title">EyeRhythm</div>
            <div className="topbar__tag">Blink companion</div>
          </div>
        </div>
        <div className="topbar__status">
          <span
            className={`status-dot ${
              connected && state.camera_ok
                ? "ok"
                : connected
                  ? "warn"
                  : "bad"
            }`}
          />
          <span className="status-text">
            {!connected
              ? "Connecting…"
              : state.camera_ok
                ? "Live"
                : state.camera_message || "Camera"}
          </span>
        </div>
      </header>

      <main className="dashboard">
        <HeroPanel
          state={state}
          avatarId={avatarId}
          onAvatarChange={persistAvatar}
        />

        <div className="target-strip" role="note">
          <span className="target-strip__label">Target rhythm</span>
          <span className="target-strip__value">
            ≈ 15–20 blinks/min while working
          </span>
        </div>

        <section className="metrics-grid" aria-label="Blink metrics">
          <MetricCard
            title="Continuous rate"
            value={formatBpm(state.continuous_bpm)}
            unit="/min"
            subtitle="last ~60s"
            tone={bpmTone}
            palette="sage"
          />
          <MetricCard
            title="Average rate"
            value={formatBpm(state.average_bpm)}
            unit="/min"
            subtitle="today"
            tone={avgTone}
            palette="mint"
          />
          <MetricCard
            title="Screen time"
            value={state.screen_time}
            subtitle="face visible today"
            tone="neutral"
            palette="peach"
          />
          <MetricCard
            title="FPS"
            value={state.fps > 0 ? state.fps.toFixed(0) : "—"}
            subtitle="camera pipeline"
            tone="neutral"
            palette="sky"
          />
          <MetricCard
            title="Regularity"
            value={regValue}
            unit={state.regularity_ready ? "/100" : undefined}
            subtitle={regSub}
            tone={regTone}
            palette="sun"
          />
          {/* Always full-width gray card: tips + famous quotes (practice mode overlays coach) */}
          <InfoQuoteCard
            practice={Boolean(state.practice)}
            practicePhase={state.practice_phase ?? "off"}
            countdownS={state.practice_countdown_s ?? 0}
            remainingS={state.practice_remaining_s ?? 0}
          />
        </section>
      </main>

      <div className="shell-footer">
        <ControlsBar state={state} />
      </div>

      {/* Full-screen practice: countdown + ball/string visual coach */}
      <PracticeScreen state={state} />
    </div>
  );
}
