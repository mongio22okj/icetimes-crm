# Phase 6c — Files Implementation Plan

> Use superpowers:subagent-driven-development or executing-plans.

**Goal:** Per-user file browser with folder hierarchy, upload, rename, delete. No preview, no sharing, local storage only. 10MB upload cap.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase6c-files-design.md`](../specs/2026-04-25-phase6c-files-design.md)

**6 commits:**

1. Folder + File models + factories + tests
2. Views + URLs + tests
3. Browser template + upload/folder forms
4. Sidebar + folder icon
5. seed_demo (uses ContentFile)
6. E2E tests

---

## Pre-flight

- [ ] Baseline: 347 unit + 44 E2E green on main
- [ ] Branch: phase6c-files (already)

---

## Task 1 — Models

`apps/files/{__init__,apps,models}.py`. Folder with parent self-FK + uniqueness on (owner, parent, name). File with FileField uploaded to `user_files/%Y/%m/`. Override File.delete to remove storage.

**Tests:** ancestors, unique constraint, delete-removes-storage.

**Commit:** `feat(files): Folder + File models with cascading delete`

---

## Task 2 — Views + URLs

9 routes per spec. UploadView accepts multiple files, enforces 10MB. DownloadView serves with proper content-type.

**Tests:** access, browser scoping, upload, download, oversized-rejection, cross-user 404, rename.

**Commit:** `feat(files): browser + upload + CRUD views with 10MB cap`

---

## Task 3 — Browser template + forms

`templates/files/browser.html` shows folders + files with breadcrumbs and Upload / New folder CTAs. `upload.html`, `folder_form.html`, `rename.html`.

**Commit:** `feat(files): browser UI + upload/rename/folder forms`

---

## Task 4 — Sidebar + icon

`Files` NavItem under Apps. Add `folder` icon. Update test_navigation.

**Commit:** `feat(core): Files sidebar entry + folder icon`

---

## Task 5 — seed_demo

Create ~3 folders + ~8 files (ContentFile in-memory bytes) for demo user.

**Commit:** `feat(seed): demo folders + files for files browser`

---

## Task 6 — E2E

3 flows: browser shows seeded contents, create folder, upload file.

**Commit:** `test(e2e): files browser + folder + upload`
