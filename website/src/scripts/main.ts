import { site } from "../config";

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

function initPurchase() {
  const dialog = document.querySelector<HTMLDialogElement>("#purchase-dialog");
  if (!dialog) return;

  const openers = document.querySelectorAll("[data-open-purchase]");
  const closers = document.querySelectorAll("[data-close-purchase]");

  const form = dialog.querySelector<HTMLFormElement>("#purchase-form");
  const success = dialog.querySelector("[data-form-success]");
  const error = dialog.querySelector("[data-form-error]");

  const reset = () => {
    form?.removeAttribute("style");
    form?.reset();
    success?.classList.remove("is-on");
    error?.classList.remove("is-on");
  };

  openers.forEach((btn) => {
    btn.addEventListener("click", () => {
      reset();
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

function validEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function initForm() {
  const form = document.querySelector<HTMLFormElement>("#purchase-form");
  const error = document.querySelector("[data-form-error]");
  const success = document.querySelector("[data-form-success]");
  const mailtoSlot = document.querySelector("[data-mailto-slot]");
  if (!form) return;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const platform = String(data.get("platform") || "both");
    const note = String(data.get("note") || "").trim();

    if (!name || !validEmail(email)) {
      error?.classList.add("is-on");
      return;
    }
    error?.classList.remove("is-on");

    const order = {
      name,
      email,
      platform,
      note,
      amount: site.price.amount,
      currency: site.price.currency,
      createdAt: new Date().toISOString(),
    };

    try {
      const key = "eyerhythm-license-reservations";
      const prev = JSON.parse(localStorage.getItem(key) || "[]") as unknown[];
      prev.push(order);
      localStorage.setItem(key, JSON.stringify(prev));
    } catch {
      /* private mode */
    }

    form.style.display = "none";
    success?.classList.add("is-on");

    if (site.contactEmail && mailtoSlot) {
      const body = encodeURIComponent(
        `Name: ${name}\nEmail: ${email}\nPlatform: ${platform}\nNote: ${note}\n`,
      );
      const subject = encodeURIComponent("EyeRhythm license reservation");
      mailtoSlot.innerHTML = `<a href="mailto:${site.contactEmail}?subject=${subject}&body=${body}">Email this reservation</a>`;
    }
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
  const dashes = Array.from(
    document.querySelectorAll<HTMLButtonElement>("[data-hero-dash]"),
  );
  const caption = document.querySelector("[data-hero-caption]");
  const slides = stage?.querySelectorAll<HTMLElement>("[data-slide]");
  if (!stage || !dashes.length || !slides?.length) return;

  const labels = dashes.map(
    (btn) =>
      btn.getAttribute("data-caption") || btn.getAttribute("aria-label") || "",
  );

  const show = (index: number) => {
    slides.forEach((slide, i) => {
      slide.classList.toggle("is-on", i === index);
    });
    dashes.forEach((btn, i) => {
      btn.setAttribute("aria-selected", i === index ? "true" : "false");
    });
    if (caption) caption.textContent = labels[index] || "";
  };

  dashes.forEach((btn) => {
    btn.addEventListener("click", () => {
      const index = Number(btn.dataset.heroDash);
      if (Number.isFinite(index)) show(index);
    });
  });
}

onReady(() => {
  initNav();
  initPurchase();
  initForm();
  initDownloadHint();
  initLivingMock();
  initRails();
  initHeroPager();
});
