from django import forms

from apps.core.widgets import (
    Combobox,
    FloatingLabelInput,
    FloatingLabelTextarea,
)
from apps.customers.models import Customer
from apps.projects.models import Milestone, Project, ProjectTask


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            "name", "description", "status", "priority",
            "customer", "due_date", "start_date", "budget", "progress",
        )
        widgets = {
            "name":        FloatingLabelInput(floating_label="Project name"),
            "description": FloatingLabelTextarea(
                floating_label="Description", rows=4, max_rows=12,
                max_length_counter=True, attrs={"maxlength": "2000"},
            ),
            "customer":    Combobox(placeholder="Pick a customer…"),
            "due_date":    forms.DateInput(attrs={"type": "date"}),
            "start_date":  forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.all()
        self.fields["customer"].required = False


class ProjectTaskForm(forms.ModelForm):
    class Meta:
        model = ProjectTask
        fields = ("title", "description", "status", "priority", "assignee", "due_date")
        widgets = {
            "title":       FloatingLabelInput(floating_label="Task title"),
            "description": FloatingLabelTextarea(
                floating_label="Description", rows=3, max_rows=10,
            ),
            "assignee":    Combobox(placeholder="Pick an assignee…"),
            "due_date":    forms.DateInput(attrs={"type": "date"}),
        }


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ("title", "due_date")
        widgets = {
            "title":    FloatingLabelInput(floating_label="Milestone title"),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
