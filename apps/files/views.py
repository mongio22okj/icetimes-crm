"""Files browser + upload + CRUD views.

Owner-scoped throughout — get_object_or_404(..., owner=request.user)
gates everything. Upload enforces a 10MB per-file cap.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.files.forms import FolderForm, RenameForm
from apps.files.models import File, Folder

UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


class _FilesMixin(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin):
    breadcrumb_title = "Files"


class BrowserView(_FilesMixin, TemplateView):
    template_name = "files/browser.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = kwargs.get("pk")
        if pk:
            current = get_object_or_404(Folder, pk=pk, owner=self.request.user)
        else:
            current = None
        ctx["current"] = current
        ctx["folders"] = Folder.objects.filter(
            owner=self.request.user, parent=current,
        ).order_by("name")
        ctx["files"] = File.objects.filter(
            owner=self.request.user, folder=current,
        )
        if current:
            ctx["file_breadcrumbs"] = current.ancestors() + [current]
        else:
            ctx["file_breadcrumbs"] = []
        return ctx


class FolderCreateView(_FilesMixin, View):
    def get(self, request):
        parent_pk = request.GET.get("parent")
        return render(request, "files/folder_form.html", {
            "form": FolderForm(),
            "parent_pk": parent_pk,
        })

    def post(self, request):
        parent_pk = request.POST.get("parent")
        parent = None
        if parent_pk:
            parent = get_object_or_404(Folder, pk=parent_pk, owner=request.user)
        form = FolderForm(request.POST)
        if not form.is_valid():
            return render(request, "files/folder_form.html", {
                "form": form, "parent_pk": parent_pk,
            })
        folder = form.save(commit=False)
        folder.owner = request.user
        folder.parent = parent
        folder.save()
        messages.success(request, "Folder created.")
        return redirect("files:folder", pk=parent.pk) if parent else redirect("files:root")


class FolderRenameView(_FilesMixin, View):
    def get(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk, owner=request.user)
        return render(request, "files/rename.html", {
            "form": RenameForm(initial={"name": folder.name}),
            "target_label": folder.name,
            "post_url": request.path,
        })

    def post(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk, owner=request.user)
        form = RenameForm(request.POST)
        if form.is_valid():
            folder.name = form.cleaned_data["name"]
            folder.save(update_fields=["name"])
            messages.success(request, "Folder renamed.")
        if folder.parent:
            return redirect("files:folder", pk=folder.parent.pk)
        return redirect("files:root")


class FolderDeleteView(_FilesMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        folder = get_object_or_404(Folder, pk=pk, owner=request.user)
        parent = folder.parent
        folder.delete()
        messages.success(request, "Folder deleted.")
        if parent:
            return redirect("files:folder", pk=parent.pk)
        return redirect("files:root")


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
        accepted = 0
        for f in files:
            if f.size > UPLOAD_MAX_BYTES:
                messages.error(request, f"{f.name} exceeds 10MB limit.")
                continue
            File.objects.create(
                owner=request.user,
                folder=folder,
                file=f,
                original_name=f.name,
                size=f.size,
                content_type=f.content_type or "",
            )
            accepted += 1
        if accepted:
            messages.success(request, f"Uploaded {accepted} file(s).")
        return redirect("files:folder", pk=folder.pk) if folder else redirect("files:root")


class DownloadView(_FilesMixin, View):
    def get(self, request, pk):
        f = get_object_or_404(File, pk=pk, owner=request.user)
        response = FileResponse(
            f.file.open("rb"),
            as_attachment=True,
            filename=f.original_name,
        )
        if f.content_type:
            response["Content-Type"] = f.content_type
        return response


class FileRenameView(_FilesMixin, View):
    def get(self, request, pk):
        f = get_object_or_404(File, pk=pk, owner=request.user)
        return render(request, "files/rename.html", {
            "form": RenameForm(initial={"name": f.original_name}),
            "target_label": f.original_name,
            "post_url": request.path,
        })

    def post(self, request, pk):
        f = get_object_or_404(File, pk=pk, owner=request.user)
        form = RenameForm(request.POST)
        if form.is_valid():
            f.original_name = form.cleaned_data["name"]
            f.save(update_fields=["original_name"])
            messages.success(request, "File renamed.")
        if f.folder:
            return redirect("files:folder", pk=f.folder.pk)
        return redirect("files:root")


class FileDeleteView(_FilesMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        f = get_object_or_404(File, pk=pk, owner=request.user)
        folder = f.folder
        f.delete()
        messages.success(request, "File deleted.")
        if folder:
            return redirect("files:folder", pk=folder.pk)
        return redirect("files:root")
