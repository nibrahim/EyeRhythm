/**
 * First-run license gate: paste the Lemon Squeezy key from the purchase email.
 *
 * Packaged Mac/Windows copies require this once, with the internet.
 * Later launches read a local file and stay offline.
 */

import { useCallback, useEffect, useState } from "react";
import { activateLicense } from "../api";
import { setSplashLayout, whenBridgeReady } from "../bridge";
import { Logo } from "./Logo";

interface Props {
  platformLabel: string;
  onActivated: () => void;
}

export function LicenseScreen({ platformLabel, onActivated }: Props) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void whenBridgeReady().then((ready) => {
      if (!cancelled && ready) void setSplashLayout(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = useCallback(async () => {
    const trimmed = key.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError("");
    try {
      const status = await activateLicense(trimmed);
      if (status.activated) {
        onActivated();
        return;
      }
      setError("Lemon Squeezy did not activate this key.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not activate this license key.",
      );
    } finally {
      setBusy(false);
    }
  }, [busy, key, onActivated]);

  return (
    <div
      className="splash"
      role="dialog"
      aria-modal="true"
      aria-labelledby="license-title"
    >
      <div className="splash__panel">
        <header className="splash__head">
          <Logo size={32} />
          <div className="splash__brand">
            <div id="license-title" className="splash__title">
              EyesRhythm
            </div>
            <div className="splash__tag">Activate this copy</div>
          </div>
        </header>

        <div className="splash__body">
          <h2 className="splash__question">Paste your license key</h2>
          <p className="splash__lead">
            It is in the email Lemon Squeezy sent after you paid. This{" "}
            {platformLabel} computer needs the internet once. After that,
            EyesRhythm stays on this machine.
          </p>
          <label className="splash__field">
            <span>License key</span>
            <input
              className="splash__key"
              type="text"
              name="license-key"
              autoComplete="off"
              spellCheck={false}
              autoFocus
              placeholder="ER-XXXX-XXXX-XXXX"
              value={key}
              disabled={busy}
              onChange={(e) => {
                setKey(e.target.value);
                if (error) setError("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void submit();
                }
              }}
            />
          </label>
          {error ? (
            <p className="splash__error" role="alert">
              {error}
            </p>
          ) : null}
          <ol className="splash__notes">
            <li className="splash__note">
              <span className="splash__note-n" aria-hidden>
                1
              </span>
              <div>
                <div className="splash__note-title">One computer, one OS</div>
                <p className="splash__note-body">
                  A purchase is for {platformLabel} on this machine. The Mac
                  and Windows copies are separate.
                </p>
              </div>
            </li>
            <li className="splash__note">
              <span className="splash__note-n" aria-hidden>
                2
              </span>
              <div>
                <div className="splash__note-title">Then you are offline</div>
                <p className="splash__note-body">
                  Camera frames and blink metrics never leave this computer.
                  Activation only tells Lemon Squeezy that this machine may
                  run your copy.
                </p>
              </div>
            </li>
          </ol>
        </div>

        <footer className="splash__foot">
          <span className="splash__hint">
            {busy ? "Talking to Lemon Squeezy…" : "Needs the internet this once"}
          </span>
          <button
            type="button"
            className="splash__cta"
            disabled={busy || !key.trim()}
            onClick={() => void submit()}
          >
            {busy ? "Activating…" : "Activate"}
          </button>
        </footer>
      </div>
    </div>
  );
}
