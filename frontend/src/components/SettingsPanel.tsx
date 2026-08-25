/**
 * Live Settings dock: ORI threshold, writing angle, blink sensitivity.
 * Changes apply immediately; each committed change is written to audit.json.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchAudit,
  fetchSettings,
  saveSettings,
  type AuditEntry,
  type LiveSettings,
} from "../api";

const DEFAULTS: LiveSettings = {
  ori_threshold: 50,
  writing_angle_deg: 20,
  turn_angle_deg: 50,
  close_delta: 0.18,
};

export function SettingsPanel() {
  const [values, setValues] = useState<LiveSettings>(DEFAULTS);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const timerRef = useRef<number | null>(null);
  const pendingRef = useRef<Partial<LiveSettings>>({});

  const reloadAudit = useCallback(() => {
    void fetchAudit(8)
      .then(setAuditLog)
      .catch(() => {
        /* keep last */
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchSettings()
      .then((s) => {
        if (!cancelled) setValues({ ...DEFAULTS, ...s });
      })
      .catch(() => {
        /* defaults */
      });
    reloadAudit();
    return () => {
      cancelled = true;
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
    };
  }, [reloadAudit]);

  const commit = useCallback(
    (patch: Partial<LiveSettings>) => {
      pendingRef.current = { ...pendingRef.current, ...patch };
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => {
        const send = pendingRef.current;
        pendingRef.current = {};
        void saveSettings(send)
          .then((s) => {
            setValues((prev) => ({ ...prev, ...s }));
            reloadAudit();
          })
          .catch(() => {
            /* engine restarting */
          });
      }, 220);
    },
    [reloadAudit],
  );

  const setNum = (key: keyof LiveSettings, raw: number) => {
    if (!Number.isFinite(raw)) return;
    setValues((prev) => ({ ...prev, [key]: raw }));
    commit({ [key]: raw });
  };

  return (
    <div className="settings">
      <label className="settings__field">
        <div className="settings__row">
          <span className="settings__name">ORI threshold</span>
          <span className="settings__value">{Math.round(values.ori_threshold)}</span>
        </div>
        <input
          type="range"
          min={20}
          max={80}
          step={1}
          value={values.ori_threshold}
          onChange={(e) => setNum("ori_threshold", Number(e.target.value))}
        />
        <p className="settings__help">
          Low-ORI line for Alert and Trace (default 50). Alert beeps after ORI
          stays below this for 3 minutes in the last 5. The red dotted Trace
          line moves with this value.
        </p>
      </label>

      <label className="settings__field">
        <div className="settings__row">
          <span className="settings__name">Writing angle</span>
          <span className="settings__value">
            {Math.round(values.writing_angle_deg)}°
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={40}
          step={1}
          value={values.writing_angle_deg}
          onChange={(e) => setNum("writing_angle_deg", Number(e.target.value))}
        />
        <p className="settings__help">
          Downward look (bottom / left-bottom / right-bottom) treated as
          off-screen. At the default 20°, a glance of 20° or more pauses blink
          counting, regularity, and Alert, and cuts Trace. Lower (10–15°) is
          stricter for close keyboard work; higher (30–40°) keeps counting while
          you look at notes.
        </p>
      </label>

      <label className="settings__field">
        <div className="settings__row">
          <span className="settings__name">Turn angle</span>
          <span className="settings__value">
            {Math.round(values.turn_angle_deg)}°
          </span>
        </div>
        <input
          type="range"
          min={20}
          max={80}
          step={1}
          value={values.turn_angle_deg}
          onChange={(e) => setNum("turn_angle_deg", Number(e.target.value))}
        />
        <p className="settings__help">
          Left or right look treated as off-screen. At the default 50°, turning
          past 50° yaw pauses blink counting, regularity, and Alert, and cuts
          Trace — the same as looking down past the writing angle. Lower is
          stricter (a smaller head turn counts as away); higher allows a wider
          side glance.
        </p>
      </label>

      <label className="settings__field">
        <div className="settings__row">
          <span className="settings__name">Blink sensitivity</span>
          <span className="settings__value">
            {values.close_delta.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0.1}
          max={0.3}
          step={0.01}
          value={values.close_delta}
          onChange={(e) => setNum("close_delta", Number(e.target.value))}
        />
        <p className="settings__help">
          How far the eyes must close above the open-eye baseline before a
          blink counts. Lower catches weaker or incomplete blinks (more
          sensitive). Higher needs a clearer closure (fewer false counts; may
          miss soft blinks or glasses).
        </p>
      </label>

      <section className="settings__audit" aria-label="Settings audit log">
        <div className="settings__name">Recent changes</div>
        {auditLog.length === 0 ? (
          <p className="settings__help">No changes yet this device.</p>
        ) : (
          <ul className="settings__audit-list">
            {auditLog.map((e, i) => (
              <li key={`${e.at}-${e.setting}-${i}`}>
                <span className="settings__audit-at">{e.at.replace("T", " ")}</span>
                <span className="settings__audit-what">
                  {e.label || e.setting}: {String(e.from)} → {String(e.to)}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="settings__help">
          Written to a local audit.json with date and time. Nothing is uploaded.
        </p>
      </section>
    </div>
  );
}
