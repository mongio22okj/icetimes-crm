# Phase 5b — Chat Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 1:1 chat between staff users. Conversation list (left sub-sidebar) + message stream (right pane). HTMX polls every 3s for new messages on the active conversation. New messages emit `new_chat` notifications via Phase 4c.

**Architecture:** Single `ChatMessage` table; no Conversation model — partners are derived. Two-pane layout (conversation list | stream), distinct from Mail's three-pane shell.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase5b-chat-design.md`](../specs/2026-04-25-phase5b-chat-design.md)

**6 commits:**

1. ChatMessage model + factory + tests
2. Views + URLs + view tests
3. Two-pane templates + sidebar entry + icon
4. New-chat notification kind + dispatch helper
5. seed_demo
6. E2E tests

---

## Pre-flight

- [ ] Baseline: 299 unit + 35 E2E green on main
- [ ] Branch: phase5b-chat (already)

---

## Task 1 — ChatMessage model

`apps/chat/{__init__,apps,models}.py`. Register in INSTALLED_APPS. Generate migration.

**Tests (~5):** `conversation_for`, `unread_from`, `partners_for` (count + ordering), empty case.

**Commit:** `feat(chat): ChatMessage model with conversation queryset`

---

## Task 2 — Views + URLs

5 routes: home, new, conversation, send, stream. View tests cover access control + send flow + mark-read on view + stream returns updated content.

**Note:** Send view uses `notify_new_chat` from `apps.notifications.dispatch` — pull forward like Mail did, since views need it.

**Commit:** `feat(chat): home/conversation/send/stream views + URLs`

---

## Task 3 — Two-pane templates

```text
templates/chat/
├── _layout.html         # extends layouts/dashboard.html, two panes
├── _conversation_list.html
├── _message_bubble.html
├── _message_stream.html # HTMX-targetable
├── home.html
└── conversation.html
```

Add `Chat` NavItem under "Apps" group. Add `message-circle` icon. Update `test_navigation` expected labels.

**Commit:** `feat(chat): two-pane layout + sidebar entry + message-circle icon`

---

## Task 4 — New-chat notification

Already wired in Task 2 (forced by import). This commit is just the migration + dispatch helper if not yet done. (May fold into Task 1 or 2.)

If Task 2 already added the kind + helper, this task becomes: add `notify_new_chat` test in `test_dispatch.py`.

**Commit:** `feat(notifications): new_chat kind + dispatch test`

---

## Task 5 — seed_demo

Add ~30 chat messages between demo and the 4 mail partners (now staff). Mix of who-sent-to-whom; some recent unread.

**Commit:** `feat(seed): chat messages between demo and staff partners`

---

## Task 6 — E2E

`tests/e2e/test_chat.py` — 3 flows:
1. Home shows seeded conversations
2. Open conversation → bubbles render
3. Send message → appears in stream

**Commit:** `test(e2e): chat home + conversation + send flows`

---

## Done

- [ ] ~12 new unit + 3 new E2E tests passing
- [ ] Sidebar shows Chat under Apps, next to Mail
- [ ] Demo has at least 3 conversations on first visit
- [ ] Sending a message dispatches notify_new_chat
