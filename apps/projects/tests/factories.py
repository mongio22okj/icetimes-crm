import factory
from factory.django import DjangoModelFactory

from apps.projects.models import Milestone, Project, ProjectTask


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Project {n}")
    description = factory.Faker("paragraph", nb_sentences=3)
    status = "active"
    priority = "med"
    progress = factory.Faker("random_int", min=0, max=100)


class MilestoneFactory(DjangoModelFactory):
    class Meta:
        model = Milestone

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Milestone {n}")


class ProjectTaskFactory(DjangoModelFactory):
    class Meta:
        model = ProjectTask

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Task {n}")
    status = "todo"
    priority = "med"
