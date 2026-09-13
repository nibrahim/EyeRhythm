# EyesRhythm release notes

## 1.2.0 — 13 September 2026

Hybrid multi-camera support. If you have more than one desk webcam (built-in plus USB), you can use them together instead of picking a single camera.

### Hybrid camera

- New **Hybrid** choice on the launch splash and in Settings. It uses every desk camera on the computer at once. Phone, iPad, and Continuity cameras stay out of the list.
- Each frame is grabbed from all desk cameras at the same instant, then blink detection runs on the camera that has a **front-facing** face, so one physical blink is counted once.
- Hybrid does not use the single-camera FPS cap (no 30 / 1 fps pacing and no post-blink pause). Detection stays on the active camera so the live FPS stays close to a single-camera session; the other cameras are checked when you turn toward them.
- If the built-in camera fails to open while the USB camera is already running, Hybrid retries the full set instead of staying on one camera.

### Also in this build

- Camera picker and Settings still let you use a single desk camera, same as 1.1.0.
- Packaged copies remain a one-time Dodo license, on-device only after activation.

### Files

| Platform | Installer |
|----------|-----------|
| macOS | `EyesRhythm-1.2.0.dmg` |
| Windows | `EyesRhythm-Setup-1.2.0.exe` |

Drag the Mac app into Applications. On Windows, run Setup (per-user, no administrator account). Allow the camera when the system asks.

---

## 1.1.0 — 7 September 2026

Quieter custom alert tone. Sound mode plays the chime; Visual mode pulses the in-app mark and blinks the minimized Windows taskbar.
