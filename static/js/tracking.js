/**
 * IceTimes CRM — Landing Tracker
 * Inserire nella landing: <script src="https://icetimes.it/static/js/tracking.js"></script>
 *
 * Traccia automaticamente: visite, click CTA, invio form lead.
 *
 * Configurazione opzionale (impostare prima dello script):
 *   window.ICETIMES_CRM = {
 *     endpoint: "https://icetimes.it",   // default
 *     source:   "landing-nome",          // label del source
 *   };
 */
(function () {
  var cfg = window.ICETIMES_CRM || {};
  var BASE = (cfg.endpoint || "https://icetimes.it").replace(/\/$/, "");
  var SOURCE = cfg.source || document.location.hostname;

  var sessionId = (function () {
    var key = "ict_sid";
    var sid = sessionStorage.getItem(key);
    if (!sid) {
      sid = ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, function (c) {
        return (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16);
      });
      sessionStorage.setItem(key, sid);
    }
    return sid;
  })();

  var params = new URLSearchParams(window.location.search);

  function post(path, body) {
    fetch(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(function () {});
  }

  /* ── 1. Traccia visita ──────────────────────────────────────────── */
  post("/api/track/visit/", {
    session_id: sessionId,
    page: window.location.pathname,
    utm_source: params.get("utm_source"),
    utm_campaign: params.get("utm_campaign"),
    utm_medium: params.get("utm_medium"),
    utm_content: params.get("utm_content"),
  });

  /* ── 2. Traccia click CTA (data-track="nome-bottone") ───────────── */
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-track]");
    if (!el) return;
    post("/api/track/click/", {
      session_id: sessionId,
      button_name: el.getAttribute("data-track"),
      page: window.location.pathname,
    });
  });

  /* ── 3. Traccia invio form (data-lead-form) ─────────────────────── */
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("[data-lead-form]");
    if (!form) return;
    e.preventDefault();

    var payload = {
      session_id: sessionId,
      first_name: (form.elements["first_name"] || form.elements["nome"] || {}).value || "",
      last_name: (form.elements["last_name"] || form.elements["cognome"] || {}).value || "",
      email: (form.elements["email"] || {}).value || "",
      phone: (form.elements["phone"] || form.elements["telefono"] || {}).value || "",
      source: SOURCE,
      utm_source: params.get("utm_source"),
      utm_campaign: params.get("utm_campaign"),
    };

    post("/api/track/lead/", payload).then && post("/api/track/lead/", payload);

    fetch(BASE + "/api/track/lead/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var msg = form.querySelector("[data-success]");
        if (msg) { msg.style.display = "block"; }
        var redirect = form.getAttribute("data-redirect");
        if (redirect) { window.location.href = redirect; }
      })
      .catch(function () {});
  });

  /* ── Espone helper globale ──────────────────────────────────────── */
  window.IceTimes = {
    trackClick: function (name) {
      post("/api/track/click/", { session_id: sessionId, button_name: name, page: window.location.pathname });
    },
    createLead: function (data) {
      return fetch(BASE + "/api/track/lead/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({ session_id: sessionId, source: SOURCE }, data)),
      }).then(function (r) { return r.json(); });
    },
  };
})();
