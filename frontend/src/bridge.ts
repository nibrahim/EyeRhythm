/**
 * Optional bridge to the pywebview desktop shell
 * ==============================================
 *
 * Inside the packaged window, Python exposes a few helpers on
 * `window.pywebview.api` (resize, fullscreen). In a normal browser
 * those helpers do not exist, so every function here quietly does
 * nothing — the page still works, it just cannot change the OS window.
 */

export interface EyeRhythmBridge {
  set_camera_layout: (expanded: boolean) => Promise<void> | void;
  /** Shrink to avatars + controls, or grow to the full dashboard. */
  set_compact_layout?: (
    compact: boolean,
    height?: number,
  ) => Promise<void> | void;
  /** Expand to fullscreen for Practice; restore on exit. */
  set_practice_fullscreen?: (enabled: boolean) => Promise<void> | void;
  /** Grow a compact window for the launch splash; restore on dismiss. */
  set_splash_layout?: (enabled: boolean) => Promise<void> | void;
  /** Grow / shrink horizontally for the Settings / Reports dock. */
  set_dock_layout?: (docked: boolean) => Promise<void> | void;
}

declare global {
  interface Window {
    pywebview?: {
      api?: EyeRhythmBridge;
    };
  }
}

/** True when we are inside the native EyeRhythm window, not a browser tab. */
export function isDesktopShell(): boolean {
  return Boolean(window.pywebview?.api);
}

/** Grow / shrink the native window to fit the camera panel. */
export async function setCameraLayout(expanded: boolean): Promise<void> {
  const api = window.pywebview?.api;
  if (!api?.set_camera_layout) return;
  try {
    await api.set_camera_layout(expanded);
  } catch {
    /* browser / unsupported */
  }
}

/** Grow / shrink the native window for compact (Less) vs full dashboard. */
export async function setCompactLayout(
  compact: boolean,
  height?: number,
): Promise<void> {
  const api = window.pywebview?.api;
  if (!api?.set_compact_layout) return;
  try {
    if (height != null && Number.isFinite(height)) {
      await api.set_compact_layout(compact, Math.round(height));
    } else {
      await api.set_compact_layout(compact);
    }
  } catch {
    /* browser / unsupported */
  }
}

/** Outer window height that hugs compact content with equal top/bottom inset. */
export function measureCompactOuterHeight(): number | undefined {
  // How tall the native window should be so the compact layout has even
  // padding above the graph and below the control buttons (same inset).
  const shell = document.querySelector(".app-shell");
  const footer = document.querySelector(".shell-footer");
  if (!(shell instanceof HTMLElement) || !(footer instanceof HTMLElement)) {
    return undefined;
  }
  const styles = getComputedStyle(shell);
  const padTop = parseFloat(styles.paddingTop) || 0;
  const padBot = parseFloat(styles.paddingBottom) || padTop;
  // Footer bottom is in viewport coords; add the same inset used above the graph.
  const inner = Math.ceil(footer.getBoundingClientRect().bottom + padBot);
  if (inner < 200) return undefined;
  const chrome = Math.max(0, Math.round(window.outerHeight - window.innerHeight));
  return inner + (chrome || 28);
}

/**
 * Full-screen the native window for Practice mode.
 * Falls back to the Fullscreen API in browser mode.
 */
export async function setPracticeFullscreen(enabled: boolean): Promise<void> {
  const api = window.pywebview?.api;
  if (api?.set_practice_fullscreen) {
    try {
      await api.set_practice_fullscreen(enabled);
      return;
    } catch {
      /* try browser API below */
    }
  }

  try {
    if (enabled) {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen?.();
      }
    } else if (document.fullscreenElement) {
      await document.exitFullscreen?.();
    }
  } catch {
    /* permission / unsupported */
  }
}

/** Grow / shrink the native window for the Settings / Reports side dock. */
export async function setDockLayout(docked: boolean): Promise<void> {
  const api = window.pywebview?.api;
  if (!api?.set_dock_layout) return;
  try {
    await api.set_dock_layout(docked);
  } catch {
    /* browser / unsupported */
  }
}

/** Grow the native window for the launch splash; restore on dismiss. */
export async function setSplashLayout(enabled: boolean): Promise<void> {
  const api = window.pywebview?.api;
  if (!api?.set_splash_layout) return;
  try {
    await api.set_splash_layout(enabled);
  } catch {
    /* browser / unsupported */
  }
}

/** Wait until pywebview has injected the API (desktop only). */
export function whenBridgeReady(timeoutMs = 3000): Promise<boolean> {
  if (window.pywebview?.api) return Promise.resolve(true);
  return new Promise((resolve) => {
    const onReady = () => {
      window.clearTimeout(timer);
      resolve(Boolean(window.pywebview?.api));
    };
    const timer = window.setTimeout(() => {
      window.removeEventListener("pywebviewready", onReady);
      resolve(Boolean(window.pywebview?.api));
    }, timeoutMs);
    window.addEventListener("pywebviewready", onReady, { once: true });
  });
}
