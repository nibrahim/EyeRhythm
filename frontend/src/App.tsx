/**
 * The whole dashboard lives in this one component.
 *
 * Layout (top → bottom):
 *   1. Title bar with a Live / Connecting light
 *   2. Hero: blinking avatar (or live camera / Trace graph)
 *   3. More / Less — hide extra cards in the compact companion window
 *   4. Four metric cards + the Information & Quote strip
 *   5. Beep / Alert / Practice buttons
 *   6. Full-screen Practice overlay when that mode is on
 *
 * Live numbers arrive from the Python engine via a WebSocket
 * (`useEngineState`). Last-session avatar and compact/full layout are
 * restored from local preferences.
 */
import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { fetchLicense, fetchPreferences, savePreferences, setToggle } from "./api";
import { LicenseScreen } from "./components/LicenseScreen";
import {
  measureCompactOuterHeight,
  setCompactLayout,
  setDockLayout,
  whenBridgeReady,
} from "./bridge";
import { type AvatarId } from "./components/Avatar";
import { ControlsBar } from "./components/ControlsBar";
import { DockPanel } from "./components/DockPanel";
import { HeroPanel } from "./components/HeroPanel";
import { Logo } from "./components/Logo";
import { MetricCard } from "./components/MetricCard";
import { InfoQuoteCard } from "./components/InfoQuoteCard";
import { PracticeScreen } from "./components/PracticeScreen";
import { SplashScreen } from "./components/SplashScreen";
import { useEngineState } from "./hooks/useEngineState";
import { useRateHistory } from "./hooks/useRateHistory";
import { lookAngleTone, oriTone } from "./utils/format";

const AVATARS: AvatarId[] = ["atlas", "lumen", "vesper", "lens", "graph"];

function asAvatarId(v: unknown): AvatarId {
  // Unknown / corrupted preference → fall back to Atlas (the default face).
  if (typeof v === "string" && (AVATARS as string[]).includes(v)) {
    return v as AvatarId;
  }
  return "atlas";
}

export default function App() {
  // Live blink numbers + whether the local engine is connected.
  const { state, connected } = useEngineState();
  const [avatarId, setAvatarId] = useState<AvatarId>("atlas");
  // Compact = small companion (avatar + buttons). Expanded = full dashboard.
  const [compact, setCompact] = useState(false);
  const [dock, setDock] = useState(false);
  const [prefsReady, setPrefsReady] = useState(false);
  // Launch splash: comfort check + notices, until Start or 3 minutes.
  const [splashOpen, setSplashOpen] = useState(true);
  // Packaged copies wait here until the emailed key is activated.
  const [licenseGate, setLicenseGate] = useState<"pending" | "needed" | "ok">(
    "pending",
  );
  const [licensePlatform, setLicensePlatform] = useState("this computer");

  // Session-wide Trace history: starts at boot, survives avatar switches + minimize.
  const present = state.face_found && !state.off_screen;
  useRateHistory(
    state.ocular_rhythm_index,
    present,
    present ? state.continuous_bpm : null,
    present && state.regularity_ready ? state.regularity : null,
  );

  useEffect(() => {
    // Wait for the desktop window to inject its resize/fullscreen helpers.
    void whenBridgeReady();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const license = await fetchLicense();
        if (cancelled) return;
        const needsKey = Boolean(license.required && !license.activated);
        setLicensePlatform(license.platform_label || "this computer");
        setLicenseGate(needsKey ? "needed" : "ok");
      } catch {
        // If the local API is still coming up, do not trap the user.
        if (!cancelled) setLicenseGate("ok");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Restore last avatar (and confirm prefs API is up).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const prefs = await fetchPreferences();
        if (!cancelled) {
          setAvatarId(asAvatarId(prefs.avatar));
          // Every launch is the default GUI: More, settings panel closed.
          setCompact(false);
          setDock(false);
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
    // Update the picture immediately, then remember it for next launch.
    setAvatarId(id);
    void savePreferences({ avatar: id }).catch(() => {
      /* offline / restarting */
    });
  }, []);

  const persistCompact = useCallback((next: boolean) => {
    setCompact(next);
    void savePreferences({ compact: next }).catch(() => {
      /* offline / restarting */
    });
    // Width stays default (or 2× default if docked); only height changes.
    void setCompactLayout(next);
  }, []);

  const persistDock = useCallback((next: boolean) => {
    if (next) {
      setCompact(false);
      setDock(true);
      void savePreferences({ compact: false, dock: true }).catch(() => {
        /* offline / restarting */
      });
      void setDockLayout(true);
      return;
    }
    // Back to the default GUI (More + default width and height, panel closed).
    setDock(false);
    setCompact(false);
    void savePreferences({ compact: false, dock: false }).catch(() => {
      /* offline / restarting */
    });
    void setDockLayout(false);
  }, []);

  // Hug compact content so the gap under the buttons matches the gap
  // between the title bar and the avatar card.
  useLayoutEffect(() => {
    if (!compact || splashOpen || licenseGate !== "ok") return;
    let cancelled = false;
    const id = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (cancelled) return;
        const height = measureCompactOuterHeight();
        if (height) void setCompactLayout(true, height);
      });
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(id);
    };
  }, [compact, splashOpen, dock, licenseGate]);

  // Keyboard shortcuts (same letters shown on the bottom buttons).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (splashOpen || licenseGate !== "ok") return;
      const t = e.target as HTMLElement | null;
      // Do not steal keys while someone is typing in a field.
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      const k = e.key.toLowerCase();
      if (k === "b") void setToggle("beep");
      else if (k === "a") void setToggle("alert");
      else if (k === "p") void setToggle("practice");
      else if (k === "d") persistCompact(!compact);
      else if (k === "w") persistDock(!dock);
      else if (k === "c") {
        persistAvatar(avatarId === "lens" ? "atlas" : "lens");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [avatarId, compact, dock, persistAvatar, persistCompact, persistDock, splashOpen, licenseGate]);

  // Colour of each card: good / warn / bad / idle based on the live number.
  // “—” means we do not have a number yet (no face, or still warming up).
  const oriValue =
    state.ocular_rhythm_index !== null
      ? Math.round(state.ocular_rhythm_index)
      : "—";
  const oriSub = !present
    ? "no face"
    : state.ocular_rhythm_index === null
      ? "need a few blinks"
      : state.ocular_rhythm_full
        ? "70% rate · 30% rhythm"
        : "rate only · rhythm warming up";
  const oriCardTone = oriTone(
    state.ocular_rhythm_index,
    present,
    state.ori_threshold,
  );
  const lookTone = lookAngleTone(state.face_angle_deg, state.face_found);

  const lookValue =
    state.face_found && state.face_angle_deg !== null
      ? Math.round(state.face_angle_deg)
      : "—";
  const lookSub = !state.face_found
    ? "no face"
    : state.off_screen
      ? "off-screen"
      : state.face_direction || "straight";

  return (
    <div
      className={`app-shell${compact ? " is-compact" : ""}${dock ? " is-docked" : ""}`}
      data-prefs-ready={prefsReady ? "1" : "0"}
    >
      <div className="app-main">
      {/* Brand + camera status light (hidden in compact companion mode). */}
      <header className="topbar">
        <div className="topbar__brand">
          <Logo size={30} />
          <div>
            <div className="topbar__title">EyesRhythm</div>
            <div className="topbar__tag">Blink companion</div>
          </div>
        </div>
        <div className="topbar__status">
          <span
            className={`status-dot ${
              connected &&
              state.camera_ok &&
              (state.camera_message === "live" || !state.camera_message)
                ? "ok"
                : connected
                  ? "warn"
                  : "bad"
            }`}
          />
          <span className="status-text">
            {!connected
              ? "Connecting…"
              : state.camera_ok &&
                  (state.camera_message === "live" || !state.camera_message)
                ? "Live"
                : state.camera_message || "Camera"}
          </span>
        </div>
      </header>

      <main className="dashboard">
        {/* Avatar / Lens / Trace plus the blinks-today chip. */}
        <HeroPanel
          state={state}
          avatarId={avatarId}
          onAvatarChange={persistAvatar}
        />

        {/* Compact ↔ full dashboard. “D” on the keyboard does the same. */}
        <div className="layout-toggles">
          <button
            type="button"
            className="layout-toggle"
            onClick={() => persistCompact(!compact)}
            title={
              compact
                ? "Show rates, screen time and other cards (D)"
                : "Hide extra cards and shrink the window (D)"
            }
          >
            <span>{compact ? "More" : "Less"}</span>
            <span className="layout-toggle__chevron" aria-hidden>
              {compact ? "▾" : "▴"}
            </span>
          </button>
          <button
            type="button"
            className={`layout-toggle${dock ? " is-on" : ""}`}
            onClick={() => persistDock(!dock)}
            title={
              dock
                ? "Hide Settings and Reports (W)"
                : "Open Settings and Reports beside the companion (W)"
            }
          >
            <span>{dock ? "Hide settings" : "Settings"}</span>
            <span className="layout-toggle__chevron" aria-hidden>
              {dock ? "◂" : "▸"}
            </span>
          </button>
        </div>

        <div className="target-strip" role="note" hidden={compact}>
          <span className="target-strip__label">Target rhythm</span>
          <span className="target-strip__value">
            ≈ 15–20 blinks/min while working
          </span>
        </div>

        {/* Four live tiles + the quote card. Hidden while compact. */}
        <section
          className="metrics-grid"
          aria-label="Blink metrics"
          hidden={compact}
        >
          <MetricCard
            title="Ocular Rhythm Index"
            value={oriValue}
            unit={state.ocular_rhythm_index !== null ? "/100" : undefined}
            subtitle={oriSub}
            tone={oriCardTone}
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
            title="Look angle"
            value={lookValue}
            unit={
              state.face_found && state.face_angle_deg !== null ? "°" : undefined
            }
            subtitle={lookSub}
            tone={lookTone}
            palette="lavender"
          />
          {/* Always full-width gray card: tips + famous quotes (practice mode overlays coach) */}
          <InfoQuoteCard
            practice={Boolean(state.practice)}
            practicePhase={state.practice_phase ?? "off"}
            countdownS={state.practice_countdown_s ?? 0}
            remainingS={state.practice_remaining_s ?? 0}
            oriThreshold={state.ori_threshold ?? 50}
            alertLowMinutes={state.alert_low_minutes ?? 3}
          />
        </section>
      </main>

      <div className="shell-footer">
        <ControlsBar state={state} />
        <p className="footer-disclaimer">
          <strong>For general wellness use only.</strong> EyesRhythm is not a
          medical device and does not diagnose, treat, cure, or prevent disease —
          full disclaimer in Settings → About.
        </p>
      </div>
      </div>

      {dock ? <DockPanel /> : null}

      {/* Full-screen practice: countdown + ball/string visual coach */}
      <PracticeScreen state={state} />

      {licenseGate === "needed" ? (
        <LicenseScreen
          platformLabel={licensePlatform}
          onActivated={() => setLicenseGate("ok")}
        />
      ) : null}

      {licenseGate === "ok" && splashOpen ? (
        <SplashScreen onDone={() => setSplashOpen(false)} />
      ) : null}

      {licenseGate === "pending" ? (
        <div className="splash" role="status" aria-live="polite">
          <div className="splash__panel">
            <header className="splash__head">
              <Logo size={32} />
              <div className="splash__brand">
                <div className="splash__title">EyesRhythm</div>
                <div className="splash__tag">Checking this copy…</div>
              </div>
            </header>
          </div>
        </div>
      ) : null}
    </div>
  );
}
