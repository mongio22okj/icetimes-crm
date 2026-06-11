# Phase 6c — Files Module

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Per-user file browser with folder hierarchy. Upload, navigate, rename, delete. Owner-scoped (no sharing in v1). No preview — download only. Local FileSystemStorage; cloud storage deferred.

## Context

Per the roadmap [Phase 6c](../plans/2026-04-24-apex-parity-roadmap.md#phase-6c--files) — closes the productivity-apps surface. Mail/Chat attachments deliberately do NOT route through this module (per roadmap decision); Files is a standalone browser UI for arbitrary user uploads.

Open questions resolved:

- **Folder model:** `parent` self-FK. Recursive queries are fine at demo scale; materialized path is overkill.
- **Max upload size:** 10MB hard cap (Django `FILE_UPLOAD_MAX_MEMORY_SIZE` plus form-level guard).
- **Allowed types:** any. The dashboard is internal/staff-only; gating mime-types adds friction without security benefit at this scale.
- **Preview:** none in v1. Click → download. Image thumbnails on the listing are a future enhancement.

## Goals

Ship a usable per-user file browser — upload, navigate folders, rename, delete — with sensible UX for empty states, breadcrumbs, and a grid layout matching the dashboard's aesthetic.

## Non-goals

- Sharing files with other users
- Public links
- Preview (PDF.js, image lightbox, video player)
- Drag-and-drop file move between folders
- Bulk operations (multi-select, batch delete)
- Versioning / history
- Search across files
- Cloud storage (S3, GCS) — local FileSystemStorage only
- Mime-type whitelist
- Thumbnail generation
- File comments / tags

## Features

| Feature | Behaviour |
|---|---|
| **Browse** | `/files/` shows root contents (folders first, then files). Each folder is clickable; each file shows name + size + uploaded date with a download button. |
| **Folder navigation** | `/files/folder/<pk>/` shows that folder's contents. Breadcrumbs show ancestor chain. |
| **New folder** | Button opens form pre-filled with parent FK from URL. |
| **Upload** | Form with `<input type="file" multiple>`. POSTs all selected files to the current folder. |
| **Rename** | Per-item button → form → save. Files keep their underlying storage path; only `original_name` changes. |
| **Delete** | POST. Folder delete cascades children. File delete also removes the underlying storage file. |
| **Empty state** | Friendly placeholder with "Upload files" or "Create folder" CTAs. |

## Architecture

### URLs

```text
apex/urls.py
  /files/ → include("apps.files.urls")

apps/files/urls.py  (app_name = "files")
  ""                                  → BrowserView         (name="root")
  "folder/<int:pk>/"                  → BrowserView         (name="folder")
  "folder/new/"                       → FolderCreateView    (name="folder_create")
  "folder/<int:pk>/rename/"           → FolderRenameView    (name="folder_rename")
  "folder/<int:pk>/delete/"           → FolderDeleteView    (name="folder_delete")    # POST
  "upload/"                           → UploadView          (name="upload")
  "<int:pk>/download/"                → DownloadView        (name="download")
  "<int:pk>/rename/"                  → FileRenameView      (name="file_rename")
  "<int:pk>/delete/"                  → FileDeleteView      (name="file_delete")      # POST
```

### App layout

```text
apps/files/
├── __init__.py
├── apps.py            FilesConfig
├── models.py          Folder + File
├── forms.py           FolderForm + UploadForm + RenameForm
├── views.py           ~9 CBVs
├── urls.py
├── admin.py
├── migrations/0001_initial.py
└── tests/
    ├── factories.py   FolderFactory + FileFactory (uses ContentFile for in-memory bytes)
    ├── test_models.py
    └── test_views.py
```

### Data model

```python
# apps/files/models.py
from django.conf import settings
from django.db import models


class Folder(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="folders")
    parent = models.ForeignKey("self", on_delete=models.CASCADE,
                               null=True, blank=True, related_name="children")
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "parent", "name"],
                name="unique_folder_name_per_parent",
            ),
        ]

    def __str__(self):
        return self.name

    def ancestors(self):
        chain = []
        current = self.parent
        while current:
            chain.append(current)
            current = current.parent
        return list(reversed(chain))


class File(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="files")
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE,
                               null=True, blank=True, related_name="files")
    file = models.FileField(upload_to="user_files/%Y/%m/")
    original_name = models.CharField(max_length=255)
    size = models.IntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_name

    def delete(self, *args, **kwargs):
        # Remove the underlying storage file
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)
```

### Views — Browser

```python
class BrowserView(_FilesMixin, TemplateView):
    template_name = "files/browser.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = kwargs.get("pk")
        if pk:
            current = get_object_or_404(Folder, pk=pk, owner=self.request.user)
        else:
            current = None
        folders = Folder.objects.filter(owner=self.request.user, parent=current).order_by("name")
        files = File.objects.filter(owner=self.request.user, folder=current)
        ctx["current"] = current
        ctx["folders"] = folders
        ctx["files"] = files
        ctx["breadcrumbs_files"] = current.ancestors() + [current] if current else []
        return ctx
```

### UploadView

```python
class UploadView(_FilesMixin, View):
    def get(self, request):
        parent_pk = request.GET.get("parent")
        return render(request, "files/upload.html", {"parent_pk": parent_pk})

    def post(self, request):
        parent_pk = request.POST.get("parent")
        folder = None
        if parent_pk:
            folder = get_object_or_404(Folder, pk=parent_pk, owner=request.user)
        files = request.FILES.getlist("files")
        for f in files:
            if f.size > 10 * 1024 * 1024:  # 10MB
                messages.error(request, f"{f.name} exceeds 10MB limit.")
                continue
            File.objects.create(
                owner=request.user, folder=folder,
                file=f, original_name=f.name, size=f.size,
                content_type=f.content_type or "",
            )
        messages.success(request, f"Uploaded {len(files)} file(s).")
        if folder:
            return redirect("files:folder", pk=folder.pk)
        return redirect("files:root")
```

### Sidebar

```python
NavItem("Files", "files:root", "folder",
        keywords=("files", "uploads", "documents"),
        group="Apps", requires_staff=True),
```

`folder` icon SVG.

## Testing

### Unit (~12 new tests)

**`test_models.py`:**
- Folder.ancestors returns root → ... → parent in order
- Folder unique constraint prevents two same-name folders under same parent
- File.delete removes underlying storage

**`test_views.py`:**
- Browser anonymous redirect, non-staff 403
- Root browser shows owner's root-level items only
- Folder browser shows that folder's contents
- Cross-user folder access 404s
- Folder create assigns owner
- Upload creates File records with size/content-type captured
- Upload rejects oversized file (>10MB)
- File download returns the file content with correct content-type
- File delete removes both DB row and storage file
- Folder rename updates `name`

### E2E (~3 new tests)

- Browser shows seeded folders + files
- Create folder flow → folder visible
- Upload a file → file visible after redirect

## Rollout — 6 commits

1. Folder + File models + factories + tests
2. Views + URLs + tests (browser, CRUD, upload, download)
3. Browser template + folder/upload/rename forms
4. Sidebar + folder icon
5. seed_demo files (uses ContentFile for in-memory uploads)
6. E2E tests
