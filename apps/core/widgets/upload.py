"""File upload widget — drag-drop multi-file with previews + XHR upload.

The widget POSTs each file individually to `upload_url` via XHR. The
endpoint must accept `multipart/form-data` with a single `file` field
and return JSON:

    {"id": "<opaque-id>", "name": "<filename>", "size": 12345,
     "url": "<download-url>", "thumbnail": "<optional-image-url>"}

Successfully uploaded file IDs are tracked in a hidden input under the
field name as a comma-separated string. The form's `clean_<field>`
hook can resolve those IDs to model instances:

    class MyForm(forms.Form):
        attachments = forms.CharField(
            required=False,
            widget=FileDropzone(upload_url="files:upload_xhr"),
        )

        def clean_attachments(self):
            ids = [pk for pk in self.cleaned_data["attachments"].split(",") if pk]
            return File.objects.filter(pk__in=ids, owner=self.user)

For the gallery demo, the upload endpoint is at `/pages/forms/_upload/`
and just synthesizes a fake response.
"""
from __future__ import annotations

from django import forms
from django.urls import reverse_lazy

from apps.core.widgets._base import WrappableWidget


class FileDropzone(WrappableWidget, forms.Widget):
    """Drag-drop file uploader.

    Args:
        upload_url: URL name (resolved via reverse_lazy) OR an absolute path
        accept: HTML accept= filter (e.g. "image/*,.pdf")
        max_files: cap on simultaneous file count
        max_size_mb: per-file size cap (UI-side; enforce server-side too)
        size: sm | md | lg
        helper: text below
    """
    template_name = "widgets/file_dropzone.html"

    def __init__(self, *, upload_url: str = "",
                 accept: str = "",
                 max_files: int = 10,
                 max_size_mb: int = 10,
                 **kwargs):
        super().__init__(**kwargs)
        self.upload_url = upload_url
        self.accept = accept
        self.max_files = max_files
        self.max_size_mb = max_size_mb

    def value_from_datadict(self, data, files, name):
        return data.get(name, "")

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        # Resolve upload_url: accept either a URL name or an absolute path.
        url = self.upload_url
        if url and not url.startswith("/") and not url.startswith("http"):
            try:
                url = str(reverse_lazy(url))
            except Exception:
                # Fall back to the raw value if not a known URL name —
                # views can pass a literal path too.
                pass
        # Initial value: comma-separated IDs (re-render after invalid POST).
        initial_ids = []
        if value:
            initial_ids = [v for v in str(value).split(",") if v.strip()]
        ctx["widget"].update({
            "upload_url": url,
            "accept": self.accept,
            "max_files": self.max_files,
            "max_size_mb": self.max_size_mb,
            "initial_ids_json": __import__("json").dumps(initial_ids),
        })
        return ctx
