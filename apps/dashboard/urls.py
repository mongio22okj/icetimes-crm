from django.urls import path
from django.views.generic import RedirectView

# The dashboard pages were removed from the IceTimes CRM — the app is a
# pure lead CRM now. We keep the URL name "dashboard" alive (logo link,
# breadcrumb root, post-login + unlock redirects all reverse it) but it
# simply bounces to the Leads list.
urlpatterns = [
    path("", RedirectView.as_view(pattern_name="leads:list", permanent=False),
         name="dashboard"),
]
