function onReady(fn: () => void) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fn);
  } else {
    fn();
  }
}

function initNav() {
  const nav = document.querySelector("[data-nav]");
  const toggle = document.querySelector<HTMLButtonElement>("[data-nav-toggle]");
  const panel = document.querySelector("[data-nav-panel]");
  if (!nav) return;

  const onScroll = () => {
    nav.classList.toggle("is-scrolled", window.scrollY > 8);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  toggle?.addEventListener("click", () => {
    const open = panel?.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  panel?.querySelectorAll("a, button").forEach((el) => {
    el.addEventListener("click", () => {
      panel.classList.remove("is-open");
      toggle?.setAttribute("aria-expanded", "false");
    });
  });
}

function initDownload() {
  const dialog = document.querySelector<HTMLDialogElement>("#download-dialog");
  if (!dialog) return;

  const openers = document.querySelectorAll("[data-open-download]");
  const closers = document.querySelectorAll("[data-close-download]");

  openers.forEach((btn) => {
    btn.addEventListener("click", () => {
      dialog.showModal();
    });
  });

  closers.forEach((btn) => {
    btn.addEventListener("click", () => dialog.close());
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
}

function initDownloadHint() {
  const ua = navigator.userAgent;
  const isMac = /Mac|iPhone|iPad/.test(ua);
  const isWin = /Windows/.test(ua);
  const pick = isMac ? "mac" : isWin ? "windows" : null;
  if (!pick) return;
  document
    .querySelector(`[data-download-card="${pick}"]`)
    ?.classList.add("is-likely");
}

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function initLivingMock() {
  const blinksEl = document.querySelector("[data-live-blinks]");
  const screenEl = document.querySelector("[data-live-screen]");
  const oriEl = document.querySelector("[data-live-ori]");
  if (!blinksEl && !screenEl && !oriEl) return;

  const tick = () => {
    const now = new Date();
    const start = new Date();
    start.setHours(9, 0, 0, 0);
    const minutes = Math.max(12, (now.getTime() - start.getTime()) / 60000);
    const blinks = Math.round(minutes * 16.4);
    const hrs = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    if (blinksEl) blinksEl.textContent = blinks.toLocaleString();
    if (screenEl) screenEl.textContent = `${hrs}h ${pad(mins)}m`;
    if (oriEl) {
      const wave = Math.round(76 + Math.sin(now.getSeconds() / 9) * 4);
      oriEl.textContent = String(wave);
    }
  };

  tick();
  window.setInterval(tick, 4000);
}

function initRails() {
  document.querySelectorAll<HTMLElement>("[data-rail]").forEach((rail) => {
    const section = rail.closest("section");
    const prev = section?.querySelector("[data-rail-prev]");
    const next = section?.querySelector("[data-rail-next]");
    const step = () => Math.min(rail.clientWidth * 0.8, 380);

    prev?.addEventListener("click", () => {
      rail.scrollBy({ left: -step(), behavior: "smooth" });
    });
    next?.addEventListener("click", () => {
      rail.scrollBy({ left: step(), behavior: "smooth" });
    });

    let down = false;
    let startX = 0;
    let startScroll = 0;

    rail.addEventListener("pointerdown", (event) => {
      down = true;
      startX = event.clientX;
      startScroll = rail.scrollLeft;
      rail.classList.add("is-dragging");
      rail.setPointerCapture(event.pointerId);
    });
    rail.addEventListener("pointermove", (event) => {
      if (!down) return;
      rail.scrollLeft = startScroll - (event.clientX - startX);
    });
    const endDrag = () => {
      down = false;
      rail.classList.remove("is-dragging");
    };
    rail.addEventListener("pointerup", endDrag);
    rail.addEventListener("pointercancel", endDrag);
  });
}

function initHeroPager() {
  const stage = document.querySelector("[data-hero-stage]");
  const rail = document.querySelector<HTMLElement>("[data-hero-rail]");
  const tabs = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-hero-dash]"),
  );
  const caption = document.querySelector("[data-hero-caption]");
  const slides = stage?.querySelectorAll<HTMLElement>("[data-slide]");
  if (!stage || !tabs.length || !slides?.length) return;
  rail?.style.setProperty("--n", String(tabs.length));

  const labels = tabs.map(
    (btn) =>
      btn.getAttribute("data-caption") || btn.getAttribute("aria-label") || "",
  );

  const show = (index: number, focusTab = false) => {
    slides.forEach((slide, i) => {
      const on = i === index;
      slide.classList.toggle("is-on", on);
      slide.setAttribute("aria-hidden", on ? "false" : "true");
    });
    tabs.forEach((btn, i) => {
      const on = i === index;
      btn.setAttribute("aria-selected", on ? "true" : "false");
      btn.tabIndex = on ? 0 : -1;
    });
    rail?.style.setProperty("--i", String(index));
    if (caption) caption.textContent = labels[index] || "";
    if (focusTab) tabs[index]?.focus();
  };

  let current = 0;
  let timer = 0;
  let paused = false;
  const waitMs = 5200;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const arm = () => {
    window.clearInterval(timer);
    if (reduced || paused) return;
    timer = window.setInterval(advance, waitMs);
  };

  const go = (index: number, focusTab = false) => {
    current = (index + tabs.length) % tabs.length;
    show(current, focusTab);
    arm();
  };

  const advance = () => {
    go(current + 1);
  };

  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      const index = Number(btn.dataset.heroDash);
      if (Number.isFinite(index)) go(index);
    });
  });

  rail?.addEventListener("keydown", (event) => {
    const key = event.key;
    let next: number | null = null;
    if (key === "ArrowRight" || key === "ArrowDown") next = current + 1;
    else if (key === "ArrowLeft" || key === "ArrowUp") next = current - 1;
    else if (key === "Home") next = 0;
    else if (key === "End") next = tabs.length - 1;
    if (next == null) return;
    event.preventDefault();
    go(next, true);
  });

  const pause = () => {
    paused = true;
    window.clearInterval(timer);
  };
  const resume = () => {
    paused = false;
    arm();
  };
  rail?.addEventListener("pointerenter", pause);
  rail?.addEventListener("pointerleave", resume);
  rail?.addEventListener("focusin", pause);
  rail?.addEventListener("focusout", resume);

  show(0);
  arm();
}

onReady(() => {
  initNav();
  initDownload();
  initDownloadHint();
  initLivingMock();
  initRails();
  initHeroPager();
});
