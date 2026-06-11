from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.customers.tests.factories import CustomerFactory
from apps.invoices.models import Invoice, InvoiceItem


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invoice

    customer = factory.SubFactory(CustomerFactory)
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    due_date = factory.LazyFunction(lambda: timezone.now().date() + timedelta(days=30))
    tax_rate = Decimal("10.00")
    notes = ""
    status = "draft"


class InvoiceItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceItem

    invoice = factory.SubFactory(InvoiceFactory)
    description = factory.Faker("sentence", nb_words=4)
    quantity = factory.Faker("pyint", min_value=1, max_value=10)
    unit_price = factory.LazyFunction(lambda: Decimal("99.00"))
