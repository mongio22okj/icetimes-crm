"""Sitemap entries for the public marketing surface.

Exposed at `/sitemap.xml` (mounted in apex/urls.py). Includes the
landing variants + pricing + support + the four Phase 18 pages
(changelog, roadmap, compare, showcase). Blog posts have their own
sitemap on `apps.blog`.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class MarketingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return [
            "marketing:hub",
            "marketing:analytics",
            "marketing:saas",
            "marketing:crm",
            "marketing:ecommerce",
            "marketing:pricing",
            "marketing:support",
            "marketing:changelog",
            "marketing:roadmap",
            "marketing:compare",
            "marketing:showcase",
        ]

    def location(self, name):
        return reverse(name)
