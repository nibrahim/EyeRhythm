/**
 * Decorative blinking avatars + live camera “Lens”
 * ================================================
 *
 * Atlas, Lumen and Vesper are drawn faces. Their eyelids close when the
 * engine reports a blink. Lens is your real webcam still. Trace (the
 * graph) and Poise (the movement map) are separate components; this file
 * only draws the faces and the picker.
 *
 * Product names are on purpose — not “camera” / “graph” in the picker.
 */

export type AvatarId = "atlas" | "lumen" | "vesper" | "lens" | "graph" | "poise";

export const AVATAR_OPTIONS: { id: AvatarId; label: string }[] = [
  { id: "atlas", label: "Atlas" },
  { id: "lumen", label: "Lumen" },
  { id: "vesper", label: "Vesper" },
  { id: "lens", label: "Lens" },
  { id: "graph", label: "Trace" },
  { id: "poise", label: "Poise" },
];

interface Props {
  id: AvatarId;
  eyesClosed: boolean;
  faceFound: boolean;
  blinkScore: number;
  /** Live JPEG url when id === "lens" */
  cameraFrameUrl?: string | null;
  cameraOk?: boolean;
  cameraMessage?: string;
}

export function Avatar({
  id,
  eyesClosed,
  faceFound,
  blinkScore,
  cameraFrameUrl,
  cameraOk,
  cameraMessage,
}: Props) {
  // Close the drawn lids on a counted close *or* a high closure score
  // (so the face feels in sync even before the state machine commits).
  const lid = eyesClosed || blinkScore > 0.45;
  // Dim the cartoon faces when nobody is in front of the camera.
  const opacity = id === "lens" ? 1 : faceFound ? 1 : 0.45;

  return (
    <div className={`avatar avatar--${id}`} style={{ opacity }} aria-hidden={id !== "lens"}>
      {id === "atlas" && <Atlas lid={lid} />}
      {id === "lumen" && <Lumen lid={lid} />}
      {id === "vesper" && <Vesper lid={lid} />}
      {id === "lens" && (
        <LensView
          frameUrl={cameraFrameUrl}
          cameraOk={cameraOk}
          cameraMessage={cameraMessage}
        />
      )}
    </div>
  );
}

/** Live camera crop (or a placeholder while the first JPEG is on its way). */
function LensView({
  frameUrl,
  cameraOk,
  cameraMessage,
}: {
  frameUrl?: string | null;
  cameraOk?: boolean;
  cameraMessage?: string;
}) {
  return (
    <div className="avatar-lens">
      {frameUrl ? (
        <img src={frameUrl} alt="Live camera" className="avatar-lens__img" />
      ) : (
        <div className="avatar-lens__placeholder">
          {cameraOk
            ? cameraMessage === "live"
              ? "Loading preview…"
              : cameraMessage || "Starting camera…"
            : cameraMessage || "Camera unavailable"}
        </div>
      )}
      <div className="avatar-lens__badge" aria-hidden>
        <CameraGlyph />
      </div>
    </div>
  );
}

/** Tiny camera icon in the corner of the Lens preview. */
function CameraGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 8.5A2.5 2.5 0 0 1 6.5 6h3l1.2-1.6A1.5 1.5 0 0 1 11.9 4h.2a1.5 1.5 0 0 1 1.2.4L14.5 6H17.5A2.5 2.5 0 0 1 20 8.5v7A2.5 2.5 0 0 1 17.5 18h-11A2.5 2.5 0 0 1 4 15.5v-7Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

/** Warm-toned portrait. `lid` true = eyes drawn as thin closed slits. */
function Atlas({ lid }: { lid: boolean }) {
  return (
    <svg viewBox="0 0 220 280" className="avatar__svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="atlasSkin" x1="40" y1="20" x2="180" y2="260">
          <stop stopColor="#D4C4B0" />
          <stop offset="0.5" stopColor="#B89A7A" />
          <stop offset="1" stopColor="#8F7358" />
        </linearGradient>
        <radialGradient id="atlasGlow" cx="50%" cy="40%" r="50%">
          <stop stopColor="rgba(107,184,160,0.3)" />
          <stop offset="1" stopColor="rgba(107,184,160,0)" />
        </radialGradient>
      </defs>
      <ellipse cx="110" cy="118" rx="88" ry="100" fill="url(#atlasGlow)" />
      <path
        d="M110 30
           C154 30 186 72 186 118
           C186 158 166 190 146 204
           L148 246 C148 262 132 270 110 270
           C88 270 72 262 72 246
           L74 204 C54 190 34 158 34 118
           C34 72 66 30 110 30Z"
        fill="url(#atlasSkin)"
        opacity="0.95"
      />
      <ellipse cx="110" cy="118" rx="50" ry="58" fill="rgba(255,255,255,0.12)" />
      <Eyes left={84} right={136} y={110} lid={lid} iris="#1A2A38" />
      <path
        d="M110 122 L110 152 M98 164 Q110 174 122 164"
        stroke="rgba(28,42,36,0.22)"
        strokeWidth="2.2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Lighter portrait with a dark hair silhouette. */
function Lumen({ lid }: { lid: boolean }) {
  return (
    <svg viewBox="0 0 220 280" className="avatar__svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="lumenSkin" x1="50" y1="10" x2="170" y2="250">
          <stop stopColor="#F0E4DC" />
          <stop offset="0.45" stopColor="#E0C8B8" />
          <stop offset="1" stopColor="#C4A090" />
        </linearGradient>
        <radialGradient id="lumenGlow" cx="50%" cy="38%" r="52%">
          <stop stopColor="rgba(232,184,150,0.4)" />
          <stop offset="1" stopColor="rgba(232,184,150,0)" />
        </radialGradient>
        <linearGradient id="lumenHair" x1="40" y1="20" x2="180" y2="100">
          <stop stopColor="#4A3A32" />
          <stop offset="1" stopColor="#2A201C" />
        </linearGradient>
      </defs>
      <ellipse cx="110" cy="120" rx="88" ry="100" fill="url(#lumenGlow)" />
      <path
        d="M110 36
           C150 36 178 74 178 118
           C178 154 162 186 146 200
           L146 244 C146 260 130 268 110 268
           C90 268 74 260 74 244
           L74 200 C58 186 42 154 42 118
           C42 74 70 36 110 36Z"
        fill="url(#lumenSkin)"
        opacity="0.96"
      />
      <path
        d="M50 100 C50 52 78 28 110 28 C142 28 170 52 170 100
           C166 72 148 52 110 50 C72 52 54 72 50 100Z
           M48 100 C44 128 46 156 56 176
           M172 100 C176 128 174 156 164 176"
        fill="url(#lumenHair)"
        opacity="0.88"
      />
      <ellipse cx="110" cy="122" rx="48" ry="56" fill="rgba(255,255,255,0.16)" />
      <Eyes left={86} right={134} y={112} lid={lid} iris="#3A2A28" highlight />
      <path
        d="M110 124 L110 148 M102 160 Q110 166 118 160"
        stroke="rgba(58,42,40,0.16)"
        strokeWidth="1.8"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Cool blue portrait with a small accent sparkle. */
function Vesper({ lid }: { lid: boolean }) {
  return (
    <svg viewBox="0 0 220 280" className="avatar__svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="vesperSkin" x1="30" y1="10" x2="190" y2="260">
          <stop stopColor="#B8D4E8" />
          <stop offset="0.4" stopColor="#8FB8D0" />
          <stop offset="1" stopColor="#6A94B0" />
        </linearGradient>
        <radialGradient id="vesperGlow" cx="50%" cy="42%" r="55%">
          <stop stopColor="rgba(140,200,255,0.45)" />
          <stop offset="0.6" stopColor="rgba(160,120,220,0.15)" />
          <stop offset="1" stopColor="rgba(100,80,200,0)" />
        </radialGradient>
        <linearGradient id="vesperAccent" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#8EC8F8" />
          <stop offset="1" stopColor="#5B9FE0" />
        </linearGradient>
      </defs>
      <ellipse cx="110" cy="120" rx="88" ry="100" fill="url(#vesperGlow)" />
      <path
        d="M110 28
           C148 28 182 64 184 112
           C186 158 166 194 148 208
           L150 246 C150 262 132 270 110 270
           C88 270 70 262 70 246
           L72 208 C54 194 34 158 36 112
           C38 64 72 28 110 28Z"
        fill="url(#vesperSkin)"
        opacity="0.94"
      />
      <path
        d="M110 28 L116 14 L110 20 L104 14 Z"
        fill="url(#vesperAccent)"
        opacity="0.9"
      />
      <ellipse cx="110" cy="118" rx="46" ry="54" fill="rgba(255,255,255,0.14)" />
      <Eyes
        left={82}
        right={138}
        y={112}
        lid={lid}
        rx={14}
        ryOpen={8}
        iris="#0E1A28"
        glow
      />
      <circle cx="62" cy="140" r="3" fill="url(#vesperAccent)" opacity="0.7" />
      <circle cx="158" cy="140" r="3" fill="url(#vesperAccent)" opacity="0.7" />
      <path
        d="M100 168 Q110 172 120 168"
        stroke="rgba(14,26,40,0.25)"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Pair of ellipses that flatten when `lid` is true (a blink). */
function Eyes({
  left,
  right,
  y,
  lid,
  rx = 12,
  ryOpen = 5.5,
  iris = "#1A2A38",
  highlight = false,
  glow = false,
}: {
  left: number;
  right: number;
  y: number;
  lid: boolean;
  rx?: number;
  ryOpen?: number;
  iris?: string;
  highlight?: boolean;
  glow?: boolean;
}) {
  const ry = lid ? 1.6 : ryOpen;
  return (
    <g className={`avatar__eyes ${lid ? "closed" : "open"}`}>
      {glow && !lid && (
        <>
          <ellipse cx={left} cy={y} rx={rx + 4} ry={ryOpen + 3} fill="rgba(91,159,224,0.28)" />
          <ellipse cx={right} cy={y} rx={rx + 4} ry={ryOpen + 3} fill="rgba(126,200,240,0.28)" />
        </>
      )}
      <ellipse cx={left} cy={y} rx={rx} ry={ry} fill={iris} />
      <ellipse cx={right} cy={y} rx={rx} ry={ry} fill={iris} />
      {!lid && (
        <>
          <circle cx={left + 2} cy={y - 1} r={highlight ? 2.2 : 2} fill="white" opacity="0.75" />
          <circle cx={right + 2} cy={y - 1} r={highlight ? 2.2 : 2} fill="white" opacity="0.75" />
          {glow && (
            <>
              <circle cx={left} cy={y} r={3.2} fill="#7EC8F0" opacity="0.55" />
              <circle cx={right} cy={y} r={3.2} fill="#5B9FE0" opacity="0.55" />
            </>
          )}
        </>
      )}
    </g>
  );
}

interface PickerProps {
  value: AvatarId;
  onChange: (id: AvatarId) => void;
}

/** Chips under the hero: Atlas / Lumen / Vesper / Lens / Trace / Poise. */
export function AvatarPicker({ value, onChange }: PickerProps) {
  return (
    <div className="avatar-picker" role="radiogroup" aria-label="Avatar style">
      {AVATAR_OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          role="radio"
          aria-checked={value === opt.id}
          className={`avatar-picker__btn ${value === opt.id ? "active" : ""}`}
          onClick={() => onChange(opt.id)}
          title={opt.label}
        >
          <span className={`avatar-picker__swatch avatar-picker__swatch--${opt.id}`} />
          <span className="avatar-picker__label">{opt.label}</span>
        </button>
      ))}
    </div>
  );
}
