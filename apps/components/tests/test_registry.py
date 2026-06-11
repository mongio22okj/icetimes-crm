"""Registry integrity tests.

Catches: duplicate slugs, unknown categories, missing/empty fields, and
primitives whose category is not present in CATEGORIES order.
"""
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import select_template

from apps.components.registry import (
    CATEGORIES,
    PRIMITIVES,
    get_primitive,
    grouped,
)


def test_slugs_are_unique():
    slugs = [p.slug for p in PRIMITIVES]
    assert len(slugs) == len(set(slugs)), "duplicate slug in PRIMITIVES"


def test_every_primitive_has_a_known_category():
    valid = {key for key, _ in CATEGORIES}
    for p in PRIMITIVES:
        assert p.category in valid, f"{p.slug}: unknown category {p.category!r}"


def test_every_primitive_has_label_and_description():
    for p in PRIMITIVES:
        assert p.label, f"{p.slug}: missing label"
        assert p.description, f"{p.slug}: missing description"
        assert p.icon, f"{p.slug}: missing icon"


def test_get_primitive_known():
    assert get_primitive("modal").label == "Modal"


def test_get_primitive_unknown_returns_none():
    assert get_primitive("not-a-primitive") is None


def test_grouped_uses_categories_order():
    out = grouped()
    seen = [g["key"] for g in out]
    expected = [k for k, _ in CATEGORIES if k in seen]
    assert seen == expected


def test_grouped_includes_every_primitive():
    flat = [p.slug for g in grouped() for p in g["items"]]
    assert sorted(flat) == sorted(p.slug for p in PRIMITIVES)


def test_every_primitive_resolves_to_a_template():
    """Either a dedicated page or the placeholder must exist."""
    for p in PRIMITIVES:
        candidates = [
            f"components/pages/{p.slug}.html",
            "components/pages/_placeholder.html",
        ]
        try:
            select_template(candidates)
        except TemplateDoesNotExist:
            raise AssertionError(f"no template found for {p.slug!r}")


def test_every_primitive_has_a_dedicated_page():
    """Every shipped primitive must have its own page (not just fall back).

    Catches: registry entries added without a backing page. The placeholder
    is defensive cover only — every entry should ship a real demo.
    """
    from django.template.exceptions import TemplateDoesNotExist
    from django.template.loader import get_template
    missing = []
    for p in PRIMITIVES:
        try:
            get_template(f"components/pages/{p.slug}.html")
        except TemplateDoesNotExist:
            missing.append(p.slug)
    assert not missing, (
        f"primitives without a dedicated page: {missing!r} — "
        "add templates/components/pages/<slug>.html or drop from registry"
    )
