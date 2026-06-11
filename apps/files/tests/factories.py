import factory
from django.core.files.base import ContentFile

from apps.accounts.tests.factories import UserFactory
from apps.files.models import File, Folder


class FolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Folder

    owner = factory.SubFactory(UserFactory)
    parent = None
    name = factory.Sequence(lambda n: f"Folder {n}")


class FileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = File

    owner = factory.SubFactory(UserFactory)
    folder = None
    file = factory.LazyFunction(
        lambda: ContentFile(b"hello world", name="seed.txt"),
    )
    original_name = "seed.txt"
    size = 11
    content_type = "text/plain"
