import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.mail.models import Message


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Message

    sender = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    subject = factory.Faker("sentence", nb_words=5)
    body = factory.Faker("paragraph", nb_sentences=3)
    sent_at = factory.LazyFunction(timezone.now)
    is_read = False
    is_starred = False
    is_trashed = False


class DraftFactory(MessageFactory):
    sent_at = None
