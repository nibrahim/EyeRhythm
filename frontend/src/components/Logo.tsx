/**
 * Tiny EyesRhythm mark used in the title bar.
 *
 * A rounded blue square with a simple eye. Drawn as SVG so it stays
 * sharp at any size; no image file is needed.
 */
export function Logo({
  size = 28,
  alertPulse = false,
}: {
  size?: number;
  /** Visual-alert: pulse the mark orange ↔ blue while the latch is on. */
  alertPulse?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className={`er-logo${alertPulse ? " is-alert-pulse" : ""}`}
    >
      <rect
        className="er-logo__mark"
        x="2"
        y="2"
        width="60"
        height="60"
        rx="18"
      />
      <ellipse
        cx="32"
        cy="32"
        rx="20"
        ry="12.5"
        stroke="white"
        strokeWidth="2.6"
        fill="rgba(255,255,255,0.14)"
      />
      <circle cx="32" cy="32" r="7.2" fill="#E8F2FA" />
      <circle cx="32" cy="32" r="3.1" fill="#1A2A38" />
      <circle cx="34.2" cy="29.8" r="1.5" fill="white" opacity="0.9" />
    </svg>
  );
}
