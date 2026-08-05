/**
 * Optional bridge to the pywebview desktop shell.
 * When running in a browser, these calls are no-ops.
 */

export interface EyeRhythmBridge {
  set_camera_layout: (expanded: boolean) => Promise<void> | void;
}

declare global {
  interface Window {
    pywebview?: {
      api?: EyeRhythmBridge;
    };
  }
}

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
