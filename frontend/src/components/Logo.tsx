/** EyeRhythm mark — solid brand blue (no gradients). */
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
