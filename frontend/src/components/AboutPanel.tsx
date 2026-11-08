/**
 * About dock tab: product identity, version, wellness disclaimer, support.
 * Static content besides Version, which comes from GET /api/health.
 */

import { useEffect, useState } from "react";
import { fetchNotices } from "../api";
import { useAppVersion } from "../hooks/useAppVersion";

const SUPPORT_EMAIL = "support@eyesrhythm.com";

export function AboutPanel() {
  const version = useAppVersion();
  const [notices, setNotices] = useState("");

  useEffect(() => {
    let cancelled = false;
    void fetchNotices()
      .then((text) => {
        if (!cancelled) setNotices(text);
      })
      .catch(() => {
        /* notices file missing in a broken freeze */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="about">
      <table className="about__table">
        <tbody>
          <tr>
            <th scope="row">Product</th>
            <td>EyesRhythm — blink rhythm companion</td>
          </tr>
          <tr>
            <th scope="row">Version</th>
            <td>{version || "—"}</td>
          </tr>
          <tr>
            <th scope="row">Description</th>
            <td>
              A privacy-first desktop companion that reads your blink rhythm
              through the webcam and nudges you back toward a healthy rate of
              roughly 15–20 blinks per minute. It also measures regularity — how
              evenly spaced your blinks are — and combines rate and regularity
              into a single Ocular Rhythm Index (ORI) scored from 0 to 100, so a
              steady rhythm counts as much as the raw count. All video is
              processed on your device; no frames, accounts, or analytics leave
              your computer.
            </td>
          </tr>
          <tr>
            <th scope="row">Disclaimer</th>
            <td>
              For general wellness use only. EyesRhythm is not a medical device.
              It has not been evaluated, cleared, or approved by the FDA or any
              other regulatory authority, and it is not intended to diagnose,
              treat, cure, or prevent any disease or condition. Blink rate, ORI,
              and gaze readings are estimates that can be affected by lighting,
              camera quality, eyewear, and head position, and should not be used
              as a basis for clinical decisions. This application is not a
              substitute for professional medical advice, diagnosis, or
              treatment. If you experience persistent eye discomfort, changes in
              vision, or other symptoms, consult a licensed eye-care
              professional.
            </td>
          </tr>
          <tr>
            <th scope="row">Support</th>
            <td>
              <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> — feature
              requests and issue reports are welcome, and we read every message.
              Reported bugs and requested features are rolled into upcoming
              versions, so stay tuned.
            </td>
          </tr>
          <tr>
            <th scope="row">Notices</th>
            <td>
              EyesRhythm is free for noncommercial use under the PolyForm
              Noncommercial License 1.0.0. Third-party libraries keep their own
              licenses (Apache 2.0, BSD, MIT, SIL OFL, and LGPLv2.1 for FFmpeg
              inside OpenCV). Those notices travel with this copy as{" "}
              <code>THIRD_PARTY_NOTICES.md</code>.
            </td>
          </tr>
        </tbody>
      </table>
      {notices ? (
        <details className="about__notices">
          <summary>Licenses in this copy</summary>
          <pre>{notices}</pre>
        </details>
      ) : null}
    </div>
  );
}
