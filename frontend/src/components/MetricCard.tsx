/**
 * One coloured tile on the dashboard (rate, ORI, screen time, …).
 *
 * The *numbers* come from the parent. This file only decides how they look:
 * title, big value, unit, small subtitle, and a pastel colour family.
 */
import type { ReactNode } from "react";

/** Distinct pastel palettes matching the reference health dashboard. */
export type CardPalette =
  | "sage"
  | "peach"
  | "sun"
  | "mint"
  | "sky"
  | "lavender"
  | "mist";

type Tone = "good" | "warn" | "bad" | "idle" | "neutral" | "future";

interface Props {
  title: string;
  value: ReactNode;
  unit?: string;
  subtitle?: string;
  tone?: Tone;
  palette?: CardPalette;
  placeholder?: boolean;
  children?: ReactNode;
}

export function MetricCard({
  title,
  value,
  unit,
  subtitle,
  tone = "neutral",
  palette = "mist",
  placeholder,
  children,
}: Props) {
  return (
    <article
      className={`metric-card palette-${palette} tone-${tone} ${
        placeholder ? "placeholder" : ""
      }`}
    >
      <header className="metric-card__head">
        <span className="metric-card__title">{title}</span>
        {subtitle ? <span className="metric-card__sub">{subtitle}</span> : null}
      </header>
      <div className="metric-card__body">
        <div className="metric-card__value-row">
          <span className="metric-card__value">{value}</span>
          {unit ? <span className="metric-card__unit">{unit}</span> : null}
        </div>
        {children}
      </div>
    </article>
  );
}
