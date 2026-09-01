/**
 * Horizontal Settings / Reports dock.
 *
 * Sits beside the companion column. More / Less still owns height;
 * this panel just scrolls inside that height.
 */

import { useState } from "react";
import { AboutPanel } from "./AboutPanel";
import { ReportsPanel } from "./ReportsPanel";
import { SettingsPanel } from "./SettingsPanel";

type Tab = "settings" | "reports" | "about";

export function DockPanel() {
  const [tab, setTab] = useState<Tab>("settings");

  return (
    <aside className="dock" aria-label="Settings, reports, and about">
      <div className="dock__tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "settings"}
          className={`dock__tab${tab === "settings" ? " is-active" : ""}`}
          onClick={() => setTab("settings")}
        >
          Settings
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "reports"}
          className={`dock__tab${tab === "reports" ? " is-active" : ""}`}
          onClick={() => setTab("reports")}
        >
          Reports
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "about"}
          className={`dock__tab${tab === "about" ? " is-active" : ""}`}
          onClick={() => setTab("about")}
        >
          About
        </button>
      </div>
      <div className="dock__body">
        {tab === "settings" ? (
          <SettingsPanel />
        ) : tab === "reports" ? (
          <ReportsPanel />
        ) : (
          <AboutPanel />
        )}
      </div>
    </aside>
  );
}
