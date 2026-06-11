"""Per-user file browser — folders + files.

Folder uses parent self-FK; ancestor walks are recursive but cheap at
demo scale. File uses Django's FileField backed by FileSystemStorage.
File.delete() also removes the underlying storage file.
"""
from django.conf import settings
from django.db import models


class Folder(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="folders",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="children",
    )
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

    def __str__(self) -> str:
        return self.name

    def ancestors(self) -> list["Folder"]:
        chain: list[Folder] = []
        current = self.parent
        while current is not None:
            chain.append(current)
            current = current.parent
        return list(reversed(chain))


class File(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="files",
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="files",
    )
    file = models.FileField(upload_to="user_files/%Y/%m/")
    original_name = models.CharField(max_length=255)
    size = models.IntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)
