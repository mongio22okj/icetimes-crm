"""WeasyPrint-backed PDF rendering for invoices.

Isolated in its own module so the import cost (~50ms) is only paid
when PDF generation is actually requested, and so tests can mock
`render_invoice_pdf` cleanly without stubbing Django's template loader.

Requires native libs (cairo, pango, gdk-pixbuf) installed on the host:
  - macOS: brew install cairo pango gdk-pixbuf libffi
  - Debian/Ubuntu: apt-get install libpango-1.0-0 libpangoft2-1.0-0
"""
from django.template.loader import render_to_string


def render_invoice_pdf(invoice, *, request=None) -> bytes:
    # Lazy import — WeasyPrint triggers cairo/pango load at import time
    from weasyprint import HTML

    html_str = render_to_string(
        "invoices/invoice_pdf.html",
        {"invoice": invoice, "items": invoice.items.all()},
        request=request,
    )
    base_url = request.build_absolute_uri("/") if request else None
    return HTML(string=html_str, base_url=base_url).write_pdf()


def weasyprint_available() -> bool:
    """Return True if WeasyPrint's native libs load. Used by tests to skip gracefully."""
    try:
        from weasyprint import HTML
        HTML(string="<p>probe</p>").write_pdf()
    except (OSError, ImportError):
        return False
    return True
