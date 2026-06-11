import factory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    kind = "invoice_sent"
    title = factory.Faker("sentence", nb_words=4)
    body = factory.Faker("sentence", nb_words=6)
    url = ""
    read_at = None
