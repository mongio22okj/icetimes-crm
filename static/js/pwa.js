// PWA bootstrap: register the service worker + capture the install prompt.
//
// Two pieces:
//   1. Register /sw.js on every page load (one-time-cost, browser handles
//      idempotency). SW updates on every deploy thanks to the cache-version
//      string baked in by the server-rendered template.
//   2. Capture the `beforeinstallprompt` event so we can show a custom
//      "Install Apex" banner instead of relying on the browser's bare
//      address-bar icon. Exposed as window.apexInstallPrompt() — an
//      Alpine factory used by templates/partials/install_banner.html.

(function () {
  // ── Service worker registration ──────────────────────────────────────
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" })
        .then((reg) => {
          // Reload once when a new SW takes control so the user sees the
          // updated build immediately. Without this, the new SW only kicks
          // in on the next nav.
          reg.addEventListener("updatefound", () => {
            const installing = reg.installing;
            if (!installing) return;
            installing.addEventListener("statechange", () => {
              if (
                installing.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                // Don't auto-reload — too jarring. Just log; the next nav
                // picks up the new SW naturally.
                console.info("[apex-pwa] new service worker installed");
              }
            });
          });
        })
        .catch((err) => console.warn("[apex-pwa] SW register failed:", err));
    });
  }

  // ── Install prompt capture ──────────────────────────────────────────
  // Browsers fire `beforeinstallprompt` when the PWA is installable but
  // not yet installed. Stashing the event lets us trigger the prompt
  // from a button click later (browsers require a user gesture).
  let deferredPrompt = null;
  let suppressed = sessionStorage.getItem("apex.installPrompt.dismissed") === "1";

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // Notify any open Alpine listeners (the banner component).
    window.dispatchEvent(new CustomEvent("apex-installable"));
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    suppressed = true;
    sessionStorage.setItem("apex.installPrompt.dismissed", "1");
    window.dispatchEvent(new CustomEvent("apex-installed"));
  });

  // ── Alpine factory for the banner ───────────────────────────────────
  window.apexInstallPrompt = function apexInstallPrompt() {
    return {
      visible: false,

      init() {
        // Show the banner if the browser already fired beforeinstallprompt
        // before this Alpine component mounted.
        if (deferredPrompt && !suppressed) this.visible = true;
        window.addEventListener("apex-installable", () => {
          if (!suppressed) this.visible = true;
        });
        window.addEventListener("apex-installed", () => {
          this.visible = false;
        });
      },

      async install() {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        deferredPrompt = null;
        this.visible = false;
        if (outcome === "dismissed") {
          // Don't pester them again this session.
          sessionStorage.setItem("apex.installPrompt.dismissed", "1");
        }
      },

      dismiss() {
        this.visible = false;
        sessionStorage.setItem("apex.installPrompt.dismissed", "1");
      },
    };
  };
})();
