/**
 * Tiny EyesRhythm mark used in the title bar.
 *
 * A rounded blue square with a pair of eyes. Drawn as SVG so it stays
 * sharp at any size; no image file is needed.
 */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="er-logo"
    >
      <rect x="2" y="2" width="60" height="60" rx="18" fill="#5B9FE0" />
      <ellipse
        cx="21.5"
        cy="32"
        rx="11"
        ry="7.5"
        stroke="white"
        strokeWidth="2.4"
        fill="rgba(255,255,255,0.14)"
      />
      <circle cx="21.5" cy="32" r="4.2" fill="#E8F2FA" />
      <circle cx="21.5" cy="32" r="2" fill="#1A2A38" />
      <circle cx="22.8" cy="30.7" r="0.85" fill="white" opacity="0.9" />
      <ellipse
        cx="42.5"
        cy="32"
        rx="11"
        ry="7.5"
        stroke="white"
        strokeWidth="2.4"
        fill="rgba(255,255,255,0.14)"
      />
      <circle cx="42.5" cy="32" r="4.2" fill="#E8F2FA" />
      <circle cx="42.5" cy="32" r="2" fill="#1A2A38" />
      <circle cx="43.8" cy="30.7" r="0.85" fill="white" opacity="0.9" />
    </svg>
  );
}
