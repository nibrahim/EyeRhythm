/**
 * Tiny EyesRhythm mark used in the title bar.
 *
 * A rounded blue square with a spaced pair of eyes and a rhythm curve
 * in the gap. Drawn as SVG so it stays sharp at any size.
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
      <path
        d="M27 33 C29.2 27.6 30.8 27.6 32 32 C33.2 36.4 34.8 36.4 37 33"
        stroke="white"
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
        opacity="0.92"
      />
      <g transform="rotate(-8 17.5 32)">
        <ellipse
          cx="17.5"
          cy="32"
          rx="8.4"
          ry="6"
          stroke="white"
          strokeWidth="2.2"
          fill="rgba(255,255,255,0.16)"
        />
        <circle cx="19.2" cy="32" r="3.4" fill="#E8F2FA" />
        <circle cx="19.6" cy="32" r="1.65" fill="#1A2A38" />
        <circle cx="20.4" cy="31.2" r="0.7" fill="white" opacity="0.95" />
      </g>
      <g transform="rotate(8 46.5 32)">
        <ellipse
          cx="46.5"
          cy="32"
          rx="8.4"
          ry="6"
          stroke="white"
          strokeWidth="2.2"
          fill="rgba(255,255,255,0.16)"
        />
        <circle cx="44.8" cy="32" r="3.4" fill="#E8F2FA" />
        <circle cx="44.4" cy="32" r="1.65" fill="#1A2A38" />
        <circle cx="45.2" cy="31.2" r="0.7" fill="white" opacity="0.95" />
      </g>
    </svg>
  );
}
