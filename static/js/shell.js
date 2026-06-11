/* eslint-disable */
// Root Alpine factory for the Apex shell: command palette + mobile drawer + theme.
// Called as x-data="apexShell()" on the dashboard layout's outer div.
window.apexShell = function apexShell() {
  return {
    // --- Shared state ---
    palette: {
      open: false,
      query: "",
      selectedIndex: 0,
      items: [],        // nav items, populated in init()
      remoteGroups: [], // [{label, icon, items: [{label, subtitle, url}]}]
      remoteLoading: false,
      _debounce: null,
      _abort: null,
    },
    drawer: { open: false },
    isMobile: false,

    init() {
      // Load palette items from the json_script payload in layouts/dashboard.html
      try {
        const script = document.getElementById("nav-items");
        this.palette.items = script ? JSON.parse(script.textContent) : [];
      } catch (e) { this.palette.items = []; }

      // Track viewport for `isMobile` (lg breakpoint = 1024px)
      const mq = window.matchMedia("(max-width: 1023px)");
      this.isMobile = mq.matches;
      mq.addEventListener("change", (e) => { this.isMobile = e.matches; });

      // Global keyboard shortcuts
      window.addEventListener("keydown", (e) => this.onGlobalKey(e));

      // Lock body scroll when palette or drawer open
      this.$watch("palette.open || drawer.open", (locked) => {
        document.body.style.overflow = locked ? "hidden" : "";
      });
      this.$watch("palette.query", (q) => {
        this.palette.selectedIndex = 0;
        this._scheduleRemoteSearch(q);
      });
    },

    onGlobalKey(e) {
      // Cmd/Ctrl + K or Cmd/Ctrl + / opens palette (works even when typing in an input).
      const isModK = (e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "/");
      if (isModK) {
        e.preventDefault();
        this.openPalette();
        return;
      }
      if (e.key === "Escape") {
        if (this.palette.open) { this.closePalette(); return; }
        if (this.drawer.open)  { this.drawer.open = false; }
      }
    },

    // --- Palette actions ---
    openPalette() {
      this._returnFocus = document.activeElement;
      this.palette.open = true;
      this.palette.query = "";
      this.palette.selectedIndex = 0;
      this.$nextTick(() => {
        const input = document.getElementById("palette-input");
        if (input) input.focus();
      });
    },
    closePalette() {
      this.palette.open = false;
      this.palette.query = "";
      this.palette.selectedIndex = 0;
      this.palette.remoteGroups = [];
      this.palette.remoteLoading = false;
      if (this.palette._abort) { try { this.palette._abort.abort(); } catch (_) {} }
      this.palette._abort = null;
      const back = this._returnFocus;
      this._returnFocus = null;
      if (back && typeof back.focus === "function") {
        this.$nextTick(() => back.focus());
      }
    },

    _scheduleRemoteSearch(q) {
      if (this.palette._debounce) clearTimeout(this.palette._debounce);
      const trimmed = (q || "").trim();
      if (trimmed.length < 2) {
        this.palette.remoteGroups = [];
        this.palette.remoteLoading = false;
        if (this.palette._abort) { try { this.palette._abort.abort(); } catch (_) {} }
        this.palette._abort = null;
        return;
      }
      this.palette.remoteLoading = true;
      this.palette._debounce = setTimeout(() => this._fetchRemote(trimmed), 200);
    },

    async _fetchRemote(q) {
      if (this.palette._abort) { try { this.palette._abort.abort(); } catch (_) {} }
      const ctl = new AbortController();
      this.palette._abort = ctl;
      try {
        const res = await fetch(`/search/?q=${encodeURIComponent(q)}`, {
          signal: ctl.signal,
          headers: { "Accept": "application/json" },
        });
        if (!res.ok) { this.palette.remoteGroups = []; return; }
        const data = await res.json();
        // Only apply if the query is still current
        if (this.palette.query.trim() === q) {
          this.palette.remoteGroups = data.groups || [];
        }
      } catch (e) {
        if (e.name !== "AbortError") this.palette.remoteGroups = [];
      } finally {
        if (this.palette.query.trim() === q) this.palette.remoteLoading = false;
      }
    },

    flatRemoteItems() {
      const out = [];
      for (const g of this.palette.remoteGroups || []) {
        for (const it of g.items || []) out.push(it);
      }
      return out;
    },
    filteredItems() {
      const q = this.palette.query.trim().toLowerCase();
      if (!q) return this.palette.items;
      return this.palette.items.filter((it) => {
        const haystack = (it.label + " " + (it.keywords || []).join(" ")).toLowerCase();
        return haystack.includes(q);
      });
    },
    allSelectableItems() {
      // Nav items first, then remote groups in order. Used for arrow-key + Enter.
      return [...this.filteredItems(), ...this.flatRemoteItems()];
    },
    moveSelection(delta) {
      const list = this.allSelectableItems();
      if (list.length === 0) return;
      this.palette.selectedIndex = (this.palette.selectedIndex + delta + list.length) % list.length;
    },
    activateSelected() {
      const list = this.allSelectableItems();
      const item = list[this.palette.selectedIndex];
      if (!item) return;
      this.closePalette();
      window.location.href = item.url;
    },
    selectionOffsetForRemoteItem(groupIdx, itemIdx) {
      // Returns the absolute index of the (groupIdx, itemIdx) in allSelectableItems.
      let offset = this.filteredItems().length;
      for (let i = 0; i < groupIdx; i++) {
        offset += (this.palette.remoteGroups[i].items || []).length;
      }
      return offset + itemIdx;
    },
    toggleTheme() {
      const el = document.documentElement;
      el.classList.toggle("dark");
      try { localStorage.setItem("theme", el.classList.contains("dark") ? "dark" : "light"); } catch (_) {}
      this.closePalette();
    },
    trapFocus(event) {
      const root = event.currentTarget;
      const focusables = root.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const visible = Array.from(focusables).filter(
        (el) => !el.disabled && el.offsetParent !== null
      );
      if (visible.length === 0) return;
      const first = visible[0];
      const last = visible[visible.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !root.contains(active)) {
          last.focus();
        } else {
          const idx = visible.indexOf(active);
          visible[idx - 1].focus();
        }
      } else {
        if (active === last) {
          first.focus();
        } else {
          const idx = visible.indexOf(active);
          visible[idx + 1 < visible.length ? idx + 1 : 0].focus();
        }
      }
    },
    iconSvg(name) {
      const bank = {
        "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
        "shopping-cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
        "package": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
        "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
        "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/>',
        "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
        "trello": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><rect width="3" height="9" x="7" y="7"/><rect width="3" height="5" x="14" y="7"/>',
        "blocks": '<rect width="7" height="7" x="14" y="3" rx="1"/><path d="M10 21V8a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5a1 1 0 0 0-1-1h-3"/>',
      };
      const body = bank[name] || "";
      return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
    },
  };
};

// ── Component primitives ────────────────────────────────────────────
// Lightweight Alpine factories for /components/ primitives. Kept here
// (vs. a separate components.js) so they're available everywhere
// base.html is loaded — no extra script tag needed.

window.apexModal = function apexModal(id) {
  return {
    open: false,
    _trigger: null,

    init() {
      // Remember the activeElement when we open, so we can restore focus on close.
      this.$watch("open", (isOpen) => {
        if (isOpen) {
          this._trigger = document.activeElement;
          // Focus the panel for screen readers.
          this.$nextTick(() => this.$el.querySelector('[role="dialog"] button')?.focus());
        } else if (this._trigger) {
          this._trigger.focus();
          this._trigger = null;
        }
      });
    },

    close() {
      this.open = false;
    },
  };
};

// Drawer — same dispatch contract as Modal, slides in from an edge.
window.apexDrawer = function apexDrawer(id) {
  return {
    open: false,
    _trigger: null,

    init() {
      this.$watch("open", (isOpen) => {
        if (isOpen) {
          this._trigger = document.activeElement;
          this.$nextTick(() => this.$el.querySelector('[role="dialog"] button')?.focus());
        } else if (this._trigger) {
          this._trigger.focus();
          this._trigger = null;
        }
      });
    },

    close() {
      this.open = false;
    },
  };
};

// Popover — local toggle with click-outside / Esc handling on the trigger.
window.apexPopover = function apexPopover() {
  return {
    open: false,
    toggle() { this.open = !this.open; },
    close() { this.open = false; },
  };
};

// Tabs — roving tabindex + arrow-key nav. Tab buttons must carry
// `data-tab="<id>"` so init() can discover order from the DOM.
window.apexTabs = function apexTabs(initial) {
  return {
    active: initial,
    _ids: [],

    init() {
      this._ids = [...this.$el.querySelectorAll('[role="tab"]')].map((b) => b.dataset.tab);
    },

    set(id) { this.active = id; },

    next() {
      if (!this._ids.length) return;
      const i = this._ids.indexOf(this.active);
      this.active = this._ids[(i + 1) % this._ids.length];
      this._focus();
    },

    prev() {
      if (!this._ids.length) return;
      const i = this._ids.indexOf(this.active);
      this.active = this._ids[(i - 1 + this._ids.length) % this._ids.length];
      this._focus();
    },

    first() {
      if (!this._ids.length) return;
      this.active = this._ids[0];
      this._focus();
    },

    last() {
      if (!this._ids.length) return;
      this.active = this._ids[this._ids.length - 1];
      this._focus();
    },

    _focus() {
      this.$nextTick(() => {
        this.$el.querySelector(`[role="tab"][data-tab="${this.active}"]`)?.focus();
      });
    },
  };
};

// Accordion — single-open by default; pass {multi: true} for multi-open
// or {initial: 'id'} to pre-open one section.
window.apexAccordion = function apexAccordion(opts = {}) {
  return {
    open: opts.initial ? [String(opts.initial)] : [],
    multi: !!opts.multi,

    isOpen(id) {
      return this.open.includes(String(id));
    },

    toggle(id) {
      const key = String(id);
      if (this.isOpen(key)) {
        this.open = this.open.filter((x) => x !== key);
      } else if (this.multi) {
        this.open = [...this.open, key];
      } else {
        this.open = [key];
      }
    },
  };
};

// Multi-select — chip-style picker with a filter input. Phase 12 ships a
// real Django form widget (apps.core.widgets.MultiSelect) on top of this
// pattern.
window.apexMultiSelect = function apexMultiSelect(opts = {}) {
  return {
    all: opts.all || [],
    selected: opts.selected || [],
    query: "",
    open: false,

    filtered() {
      const q = this.query.trim().toLowerCase();
      return this.all.filter((o) => !q || String(o).toLowerCase().includes(q));
    },

    add(value) {
      if (!this.selected.includes(value)) this.selected = [...this.selected, value];
      this.query = "";
    },

    remove(value) {
      this.selected = this.selected.filter((v) => v !== value);
    },

    removeLast() {
      if (this.selected.length) this.selected = this.selected.slice(0, -1);
    },
  };
};

// Tag input — free-form chip entry with paste-to-split.
window.apexTagInput = function apexTagInput(opts = {}) {
  return {
    tags: opts.initial || [],
    suggestions: opts.suggestions || [],
    draft: "",

    commit() {
      const v = this.draft.trim().replace(/,$/, "").trim();
      if (v && !this.tags.includes(v)) this.tags.push(v);
      this.draft = "";
    },

    add(value) {
      if (value && !this.tags.includes(value)) this.tags.push(value);
    },

    removeAt(i) {
      this.tags.splice(i, 1);
    },

    removeLast() {
      if (this.tags.length) this.tags.pop();
    },

    onPaste(e) {
      const text = (e.clipboardData || window.clipboardData).getData("text") || "";
      const parts = text.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      parts.forEach((p) => { if (!this.tags.includes(p)) this.tags.push(p); });
    },
  };
};

// Combobox — single-select typeahead over a static option list. Phase 12
// ships a real Django widget with HTMX-powered async loading.
window.apexCombobox = function apexCombobox(opts = {}) {
  return {
    all: opts.all || [],
    value: opts.value || "",
    query: "",
    open: false,
    activeIndex: 0,

    filtered() {
      const q = this.query.trim().toLowerCase();
      if (!q) return this.all;
      return this.all.filter((o) => String(o).toLowerCase().includes(q));
    },

    pick(value) {
      this.value = value;
      this.close();
    },

    pickActive() {
      const opts = this.filtered();
      if (opts.length) this.pick(opts[Math.max(0, Math.min(this.activeIndex, opts.length - 1))]);
    },

    moveDown() {
      const len = this.filtered().length;
      if (len) this.activeIndex = (this.activeIndex + 1) % len;
    },

    moveUp() {
      const len = this.filtered().length;
      if (len) this.activeIndex = (this.activeIndex - 1 + len) % len;
    },

    close() {
      this.open = false;
      this.query = "";
      this.activeIndex = 0;
    },
  };
};

// Browser-push opt-in. Reads window.APEX_PUSH = {serverPublicKey,
// subscribeUrl, unsubscribeUrl} for config. When serverPublicKey is
// empty the factory shows a "not configured" status instead of
// attempting to subscribe — useful in the template repo where VAPID
// keys aren't shipped.
window.apexPushOptIn = function apexPushOptIn() {
  return {
    enabled: false,
    status: "",

    async init() {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        this.status = "Push notifications aren't supported in this browser.";
        return;
      }
      const reg = await navigator.serviceWorker.getRegistration();
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      this.enabled = !!sub;
      if (!window.APEX_PUSH || !window.APEX_PUSH.serverPublicKey) {
        this.status = "Push isn't configured on this server (no VAPID keys). Add VAPID_PUBLIC_KEY + VAPID_PRIVATE_KEY to enable.";
      }
    },

    _csrf() {
      const m = document.cookie.match(/csrftoken=([^;]+)/);
      return m ? m[1] : "";
    },

    _b64ToUint8(b64) {
      const padding = "=".repeat((4 - (b64.length % 4)) % 4);
      const base64 = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
      const raw = atob(base64);
      const out = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
      return out;
    },

    async enable() {
      const cfg = window.APEX_PUSH || {};
      if (!cfg.serverPublicKey) {
        this.status = "Push isn't configured on this server (no VAPID keys).";
        return;
      }
      try {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") {
          this.status = "Permission denied. Re-enable in your browser settings.";
          return;
        }
        const reg = await navigator.serviceWorker.register("/static/sw.js");
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: this._b64ToUint8(cfg.serverPublicKey),
        });
        const r = await fetch(cfg.subscribeUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": this._csrf() },
          body: JSON.stringify(sub),
        });
        if (r.ok) {
          this.enabled = true;
          this.status = "Subscribed. New notifications will arrive in this browser.";
        } else {
          this.status = `Server rejected subscription (${r.status}).`;
        }
      } catch (e) {
        this.status = `Failed to enable push: ${e.message}`;
      }
    },

    async disable() {
      const cfg = window.APEX_PUSH || {};
      try {
        const reg = await navigator.serviceWorker.getRegistration();
        const sub = reg ? await reg.pushManager.getSubscription() : null;
        if (sub) {
          await fetch(cfg.unsubscribeUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": this._csrf() },
            body: JSON.stringify({ endpoint: sub.endpoint }),
          });
          await sub.unsubscribe();
        }
        this.enabled = false;
        this.status = "Unsubscribed.";
      } catch (e) {
        this.status = `Failed to disable: ${e.message}`;
      }
    },
  };
};

// Character counter helper. Wraps any input/textarea reachable via
// $refs.input. Pass the maxlength; pulls the current length from the
// input on every keystroke. The wrapping element renders the counter.
window.apexCharCounter = function apexCharCounter(maxLen) {
  return {
    n: 0,
    max: parseInt(maxLen, 10) || 0,

    init() {
      const el = this.$refs.input;
      if (el) this.n = String(el.value || "").length;
    },

    update(value) {
      this.n = String(value || "").length;
    },

    get classes() {
      if (!this.max) return "text-muted-foreground";
      const pct = this.n / this.max;
      if (pct >= 1) return "text-destructive font-medium";
      if (pct >= 0.9) return "text-amber-600";
      return "text-muted-foreground";
    },
  };
};

// Conditional reveal. Use as `x-data="apexReveal('field-id', value => …)"`
// on a wrapping element; the contents show/hide based on the watched
// field's current value. The factory listens for `input`/`change` on
// the field; pass any predicate that returns truthy to reveal.
window.apexReveal = function apexReveal(targetId, predicate) {
  return {
    visible: false,

    init() {
      const el = document.getElementById(targetId);
      if (!el) return;
      const evaluate = () => {
        try { this.visible = !!predicate(el.value); }
        catch { this.visible = false; }
      };
      evaluate();
      el.addEventListener("input", evaluate);
      el.addEventListener("change", evaluate);
    },
  };
};

// Date-range picker. Stores `from` and `to` as ISO date strings; the
// surrounding form template binds them into a single hidden input.
window.apexDateRange = function apexDateRange(opts = {}) {
  return {
    from: opts.from || "",
    to: opts.to || "",
    open: false,

    label() {
      if (!this.from || !this.to) return "Pick a date range…";
      const f = new Date(this.from + "T00:00:00").toLocaleDateString(undefined, {month: "short", day: "numeric"});
      const t = new Date(this.to + "T00:00:00").toLocaleDateString(undefined, {month: "short", day: "numeric"});
      return `${f} – ${t}`;
    },

    apply(fromOffsetDays, toOffsetDays) {
      const f = new Date(); f.setDate(f.getDate() + fromOffsetDays);
      const t = new Date(); t.setDate(t.getDate() + toOffsetDays);
      this.from = f.toISOString().slice(0, 10);
      this.to = t.toISOString().slice(0, 10);
      this.open = false;
    },

    applyMonthToDate() {
      const now = new Date();
      const f = new Date(now.getFullYear(), now.getMonth(), 1);
      this.from = f.toISOString().slice(0, 10);
      this.to = now.toISOString().slice(0, 10);
      this.open = false;
    },

    clear() {
      this.from = "";
      this.to = "";
    },
  };
};

// Auto-grow textarea — wraps a single <textarea x-ref="ta">. Pass the
// max number of rows; falls back to the default `rows` attribute when
// content is shorter. Used by FloatingLabelTextarea + RichText fallback.
window.apexAutogrow = function apexAutogrow(maxRows = 10) {
  return {
    maxRows,

    resize() {
      const ta = this.$refs.ta;
      if (!ta) return;
      // Reset so we shrink as well as grow.
      ta.style.height = "auto";
      const lineHeight = parseFloat(getComputedStyle(ta).lineHeight) || 20;
      const padding = parseFloat(getComputedStyle(ta).paddingTop)
                    + parseFloat(getComputedStyle(ta).paddingBottom);
      const maxHeight = Math.round(lineHeight * this.maxRows + padding);
      ta.style.height = Math.min(ta.scrollHeight, maxHeight) + "px";
      ta.style.overflowY = ta.scrollHeight > maxHeight ? "auto" : "hidden";
    },
  };
};

// Datatable bulk-selection state. The form wrapping the table reads
// `selected[]` to build hidden `ids` fields; the toolbar reads `selected`
// to show the count + show/hide.
window.apexBulk = function apexBulk(opts = {}) {
  return {
    selected: [],            // string IDs (HTML form values are strings)
    pageIds: (opts.pageIds || []).map(String),
    pendingAction: "",
    pendingConfirmText: "",
    confirmOpen: false,

    allOnPageSelected() {
      return this.pageIds.length > 0
        && this.pageIds.every((id) => this.selected.includes(id));
    },

    someOnPageSelected() {
      return this.pageIds.some((id) => this.selected.includes(id))
        && !this.allOnPageSelected();
    },

    toggleAllOnPage(checked) {
      if (checked) {
        const set = new Set([...this.selected, ...this.pageIds]);
        this.selected = [...set];
      } else {
        this.selected = this.selected.filter((id) => !this.pageIds.includes(id));
      }
    },

    clear() {
      this.selected = [];
    },

    ask(action, confirmText) {
      this.pendingAction = action;
      if (confirmText) {
        this.pendingConfirmText = String(confirmText).replace("{n}", this.selected.length);
        this.confirmOpen = true;
      } else {
        // No confirm needed — submit the wrapping form synchronously after
        // Alpine has had a chance to update pendingAction.
        this.$nextTick(() => this.$root.submit());
      }
    },

    confirm() {
      this.confirmOpen = false;
      this.$nextTick(() => this.$root.submit());
    },
  };
};

// File dropzone — drag-drop multi-file with previews and optional XHR upload.
// Pass `uploadUrl` to make the dropzone POST each file individually as
// multipart/form-data (single `file` field). The endpoint must return
// JSON: {id, name, size, url, thumbnail?}. The widget tracks per-file
// status (pending/uploading/done/error) + progress, and exposes
// `uploadedIds` so the surrounding form template can bind a hidden
// input to the comma-joined IDs.
window.apexDropzone = function apexDropzone(opts = {}) {
  return {
    files: [],
    accept: opts.accept || "",
    maxFiles: opts.maxFiles || 10,
    maxSizeMB: opts.maxSizeMB || 20,
    uploadUrl: opts.uploadUrl || "",
    initialIds: opts.initialIds || [],
    isDragging: false,
    error: "",

    init() {
      // Pre-populate from server-rendered initial IDs (re-render after
      // form invalid). They show up as plain {serverId, name=`#<id>`,
      // status: "done"} entries with no thumbnail.
      for (const id of this.initialIds) {
        this.files.push({
          id: `pre-${id}`,
          serverId: String(id),
          name: `#${id}`,
          size: 0,
          type: "",
          preview: null,
          status: "done",
          progress: 100,
        });
      }
    },

    get uploadedIds() {
      return this.files
        .filter((f) => f.status === "done" && f.serverId)
        .map((f) => f.serverId)
        .join(",");
    },

    onDragOver(e) {
      e.preventDefault();
      this.isDragging = true;
    },

    onDragLeave() {
      this.isDragging = false;
    },

    onDrop(e) {
      e.preventDefault();
      this.isDragging = false;
      this.addFiles(e.dataTransfer.files);
    },

    onPick(e) {
      this.addFiles(e.target.files);
      e.target.value = "";
    },

    _csrfToken() {
      const m = document.cookie.match(/csrftoken=([^;]+)/);
      return m ? m[1] : "";
    },

    addFiles(fileList) {
      this.error = "";
      const remaining = this.maxFiles - this.files.length;
      const incoming = Array.from(fileList).slice(0, remaining);
      if (fileList.length > remaining) {
        this.error = `Capped at ${this.maxFiles} files.`;
      }
      for (const f of incoming) {
        if (f.size > this.maxSizeMB * 1024 * 1024) {
          this.error = `"${f.name}" exceeds ${this.maxSizeMB} MB.`;
          continue;
        }
        const entry = {
          id: Date.now() + Math.random(),
          name: f.name,
          size: f.size,
          type: f.type,
          preview: null,
          status: "pending",
          progress: 0,
          serverId: null,
          xhr: null,
        };
        if (f.type.startsWith("image/")) {
          const reader = new FileReader();
          reader.onload = (ev) => { entry.preview = ev.target.result; };
          reader.readAsDataURL(f);
        }
        this.files.push(entry);
        if (this.uploadUrl) this._upload(entry, f);
      }
    },

    _upload(entry, file) {
      entry.status = "uploading";
      const fd = new FormData();
      fd.append("file", file);
      const xhr = new XMLHttpRequest();
      entry.xhr = xhr;
      xhr.open("POST", this.uploadUrl);
      const csrf = this._csrfToken();
      if (csrf) xhr.setRequestHeader("X-CSRFToken", csrf);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) entry.progress = Math.round((e.loaded / e.total) * 100);
      };
      xhr.onload = () => {
        entry.xhr = null;
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            entry.serverId = String(data.id || "");
            entry.status = "done";
            entry.progress = 100;
            if (data.thumbnail) entry.preview = data.thumbnail;
          } catch (_e) {
            entry.status = "error";
            entry.error = "Bad server response";
          }
        } else {
          entry.status = "error";
          entry.error = `Upload failed (${xhr.status})`;
        }
      };
      xhr.onerror = () => {
        entry.status = "error";
        entry.error = "Network error";
        entry.xhr = null;
      };
      xhr.send(fd);
    },

    cancel(id) {
      const entry = this.files.find((f) => f.id === id);
      if (entry && entry.xhr) entry.xhr.abort();
      this.remove(id);
    },

    remove(id) {
      this.files = this.files.filter((f) => f.id !== id);
    },

    clear() {
      this.files = [];
      this.error = "";
    },

    fmtSize(bytes) {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    },
  };
};

// Toasts — single instance per page, mounted by partials/toasts.html.
// Drains Django messages from the json_script payload on init, and exposes
// a global window.apexToast({level, body, action, persistent}) so any code
// can push a client-side toast without a server round trip.
window.apexToasts = function apexToasts() {
  return {
    toasts: [],
    _nextId: 1,

    init() {
      const script = document.getElementById("apex-toast-payload");
      if (script) {
        try {
          const initial = JSON.parse(script.textContent || "[]");
          (Array.isArray(initial) ? initial : []).forEach((t) => this.push(t));
        } catch (_e) { /* ignore malformed payload */ }
      }
      // Expose a global push helper. Re-bound on every init() so the latest
      // mount wins (e.g. in HTMX swaps that rebuild the container).
      window.apexToast = (toast) => this.push(toast);
    },

    push(toast) {
      const id = this._nextId++;
      const t = {
        id,
        level: toast.level || "info",
        body: toast.body || "",
        action: toast.action || null,
        persistent: !!toast.persistent,
      };
      this.toasts.push(t);
      if (!t.persistent) {
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const ms = reduce ? 8000 : 5000;
        setTimeout(() => this.dismiss(id), ms);
      }
    },

    dismiss(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id);
    },
  };
};

// Sidebar scroll persistence + auto-scroll-active.
//
// Server-rendered navigation reloads the document, which resets the
// sidebar's scrollTop to 0 — losing the active item from view if it's
// far down the list. Two complementary fixes:
//
//   1. On every page load, scroll the link with aria-current="page"
//      into view ("nearest" so it doesn't jerk the page if it's already
//      visible). Handles deep links + first visits with no JS state.
//   2. Persist the sidebar's scrollTop in sessionStorage so the user's
//      exact scroll position survives navigation — useful when they
//      were browsing a different group before clicking a link.
//
// Restore order matters: sessionStorage first (gets us close), then
// scrollIntoView({block: "nearest"}) only nudges if the active item
// is still off-screen. Result: zero flicker, zero jerk.
(function initSidebarScroll() {
  const SS_KEY = "apex.sidebar.scrollTop";
  const SEL_NAV = 'nav[aria-label="Main navigation"]';

  function restore() {
    const nav = document.querySelector(SEL_NAV);
    if (!nav) return;

    // 1. Restore last-known scrollTop (no-op if first visit).
    const saved = sessionStorage.getItem(SS_KEY);
    if (saved != null) nav.scrollTop = parseInt(saved, 10) || 0;

    // 2. Nudge the active link into view if it's still off-screen.
    //    `block: "nearest"` only scrolls when needed.
    const active = nav.querySelector('a[aria-current="page"]');
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  function persistOnClick() {
    const nav = document.querySelector(SEL_NAV);
    if (!nav) return;
    nav.addEventListener("click", (e) => {
      // Save before navigation. The link's default action navigates
      // synchronously, so this runs first.
      if (e.target.closest("a")) {
        sessionStorage.setItem(SS_KEY, String(nav.scrollTop));
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      restore();
      persistOnClick();
    });
  } else {
    restore();
    persistOnClick();
  }
})();
