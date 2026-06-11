import factory

from apps.customers.models import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
        django_get_or_create = ("email",)

    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"customer{n}@example.com")
    phone = factory.Faker("phone_number")
    company = factory.Faker("company")
    address = factory.Faker("street_address")
    city = factory.Faker("city")
    country = factory.Faker("country")
    status = "active"
