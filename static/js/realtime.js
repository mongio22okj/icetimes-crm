// Realtime WebSocket bridge.
//
// Two Alpine components are exposed on `window`:
//
//   apexNotifyStream() — connects to /ws/notifications/, refreshes the
//     bell HTMX target on incoming notifications and updates the badge
//     count without a round-trip.
//
//   apexPresence() — connects to /ws/presence/, exposes `count` for the
//     header pill, plus toast hooks for joins/leaves.
//
// Both components auto-reconnect with exponential backoff up to 30s,
// fall back gracefully when window.WebSocket is unavailable, and
// silently no-op for unauthenticated users (the consumer rejects
// anonymous connections with code 4401, which we treat as "stop trying").

(function () {
  function wsUrl(path) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${path}`;
  }

  // Tiny exponential-backoff WS wrapper. `onMessage(data)` receives
  // parsed JSON. Returns an object with .close() so callers can tear
  // down on Alpine destroy.
  function connect(path, { onMessage, onOpen, onClose } = {}) {
    let ws = null;
    let attempt = 0;
    let stopped = false;

    function open() {
      if (stopped) return;
      try {
        ws = new WebSocket(wsUrl(path));
      } catch (_e) {
        return scheduleReconnect();
      }
      ws.addEventListener("open", () => {
        attempt = 0;
        if (onOpen) onOpen();
      });
      ws.addEventListener("message", (ev) => {
        let data;
        try {
          data = JSON.parse(ev.data);
        } catch (_e) {
          return;
        }
        if (onMessage) onMessage(data);
      });
      ws.addEventListener("close", (ev) => {
        if (onClose) onClose(ev);
        // 4401 = consumer refused (e.g. anonymous). Don't bother retrying.
        if (ev.code === 4401) {
          stopped = true;
          return;
        }
        scheduleReconnect();
      });
      ws.addEventListener("error", () => {
        try { ws.close(); } catch (_e) {}
      });
    }

    function scheduleReconnect() {
      if (stopped) return;
      attempt += 1;
      const delay = Math.min(30000, 500 * Math.pow(2, attempt));
      setTimeout(open, delay);
    }

    open();
    return {
      close() {
        stopped = true;
        if (ws) try { ws.close(); } catch (_e) {}
      },
    };
  }

  window.apexNotifyStream = function apexNotifyStream() {
    return {
      connection: null,
      init() {
        if (!window.WebSocket) return;
        this.connection = connect("/ws/notifications/", {
          onMessage: (data) => this.onMessage(data),
        });
      },
      destroy() {
        if (this.connection) this.connection.close();
      },
      onMessage(data) {
        if (data.event === "notification") {
          // Refresh the bell partial so the new row appears in the dropdown.
          const bell = document.getElementById("notification-bell-content");
          if (bell && window.htmx) {
            window.htmx.trigger(bell, "refresh");
          }
          // Surface a transient toast for awareness. apexToast takes
          // {level, body, action, persistent} — merge title into body
          // and route the URL through an action button when present.
          if (window.apexToast) {
            const lines = [data.data.title];
            if (data.data.body) lines.push(data.data.body);
            window.apexToast({
              level: "info",
              body: lines.join(" — "),
              action: data.data.url
                ? { label: "View", href: data.data.url }
                : null,
            });
          }
        } else if (data.event === "unread_count") {
          this.updateBadge(data.count);
        } else if (data.event === "new_lead") {
          this.onNewLead(data.data || {});
        }
      },
      onNewLead(lead) {
        // Toast immediato (speed-to-lead).
        if (window.apexToast) {
          const who = lead.name || lead.email || "Nuovo lead";
          const where = lead.source ? ` · ${lead.source}` : "";
          window.apexToast({
            level: "success",
            body: `🎯 Nuovo lead: ${who}${where}`,
            action: { label: "Vedi", href: "/leads/" },
          });
        }
        // Beep discreto per richiamare l'attenzione.
        try {
          const Ctx = window.AudioContext || window.webkitAudioContext;
          if (Ctx) {
            const ctx = new Ctx();
            const o = ctx.createOscillator();
            const g = ctx.createGain();
            o.type = "sine";
            o.frequency.value = 880;
            g.gain.value = 0.05;
            o.connect(g); g.connect(ctx.destination);
            o.start();
            o.stop(ctx.currentTime + 0.15);
            setTimeout(() => ctx.close(), 400);
          }
        } catch (_e) {}
        // Notifica al resto della pagina (es. la dashboard può ricaricare i KPI).
        document.dispatchEvent(new CustomEvent("apex:new-lead", { detail: lead }));
      },
      updateBadge(count) {
        // Re-render badge inline without waiting on the HTMX refresh.
        const bell = document.getElementById("notification-bell-content");
        if (!bell) return;
        const button = bell.querySelector("button");
        if (!button) return;
        let badge = button.querySelector("[data-bell-badge]");
        if (count > 0) {
          if (!badge) {
            badge = document.createElement("span");
            badge.setAttribute("data-bell-badge", "");
            badge.className =
              "absolute -top-1 -right-1 h-5 min-w-5 px-1 rounded-full " +
              "bg-destructive text-destructive-foreground text-[10px] " +
              "font-semibold inline-flex items-center justify-center ring-2 ring-card";
            button.appendChild(badge);
          }
          badge.textContent = count > 99 ? "99+" : String(count);
        } else if (badge) {
          badge.remove();
        }
      },
    };
  };

  window.apexPresence = function apexPresence() {
    return {
      count: 0,
      connection: null,
      lastJoined: null,
      lastLeft: null,
      init() {
        if (!window.WebSocket) return;
        this.connection = connect("/ws/presence/", {
          onMessage: (data) => {
            if (data.event === "presence") {
              this.count = data.count;
              this.lastJoined = data.joined || null;
              this.lastLeft = data.left || null;
            }
          },
        });
      },
      destroy() {
        if (this.connection) this.connection.close();
      },
    };
  };

  // Also: support htmx's `trigger` event on the bell so server-side
  // refreshes still work even if the WS hasn't kicked in yet.
  document.addEventListener("DOMContentLoaded", () => {
    const bell = document.getElementById("notification-bell-content");
    if (bell && window.htmx) {
      bell.addEventListener("refresh", () => {
        window.htmx.trigger(bell, "load");
      });
    }
  });
})();
