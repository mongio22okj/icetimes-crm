import json
import urllib.error
import urllib.request

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_ERROR, LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from .forms import ProductForm
from .models import Category, Product, Sale


def _category_choices():
    return tuple((str(c.pk), c.name) for c in Category.objects.all())


PRODUCTS_TABLE = TableConfig(
    key="products",
    bulk_actions=(
        BulkAction(slug="publish", label="Publish", icon="check"),
        BulkAction(slug="archive", label="Archive", icon="x"),
    ),
    columns=(
        Column("name", "Product", searchable=True, pinned=True,
               template="products/_table_cells.html#product"),
        Column("sku", "SKU", searchable=True, priority=2),
        Column("category.name", "Category",
               filter=Filter("select", choices=_category_choices, label="Category"),
               priority=2),
        Column("price", "Price", sortable=True, align="right",
               filter=Filter("numeric"),
               formatter=lambda v: f"${v}" if v is not None else ""),
        Column("stock", "Stock", sortable=True, align="right",
               filter=Filter("numeric")),
        Column("status", "Status",
               filter=Filter("select", choices=Product.STATUS),
               template="products/_table_cells.html#status"),
    ),
    default_sort="-created_at",
    page_size=25,
    sticky_first=True,
    caption="Inventory and catalog.",
    empty_icon="package",
    empty_headline="No products yet",
    empty_body="Add your first product to start tracking inventory.",
)


class ProductListView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, TableView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    breadcrumb_title = "Products"
    table_config = PRODUCTS_TABLE

    def get_queryset(self):
        return super().get_queryset().select_related("category")

    def handle_bulk_action(self, action, ids, request):
        targets = Product.objects.filter(pk__in=ids)
        n = targets.count()
        if action.slug == "publish":
            targets.update(status="published")
            toast(request, LEVEL_SUCCESS, f"Published {n} products.")
        elif action.slug == "archive":
            targets.update(status="archived")
            toast(request, LEVEL_SUCCESS, f"Archived {n} products.")
        return redirect("products:list")


class ProductDetailView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"
    breadcrumb_parent = "products:list"

    def get_breadcrumb_title(self):
        return self.object.name


class ProductCreateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("products:list")
    breadcrumb_title = "New product"
    breadcrumb_parent = "products:list"


class ProductUpdateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("products:list")
    breadcrumb_parent = "products:list"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.name}"


# ── Public product landing + submit ─────────────────────────────────────

class ProductLandingView(TemplateView):
    """Public landing page for a single Product. URL: /p/<slug>/.

    Only renders when Product.status == 'published'. Form posts to
    ProductSubmitView which creates a Sale row.
    """
    template_name = "products/landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        product = get_object_or_404(Product, slug=slug, status="published")
        ctx["product"] = product
        return ctx


@method_decorator(csrf_exempt, name="dispatch")
class ProductSubmitView(View):
    """POST handler for the public product landing form.

    Creates Sale (status=pending) + Lead (for /leads/ pipeline). Returns
    JSON so the page can show inline success / redirect.
    """

    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug, status="published")
        data = request.POST
        email = (data.get("email") or "").strip()
        if not email:
            return JsonResponse({"ok": False, "error": "email required"}, status=400)

        # Capture real visitor IP (Render proxies via X-Forwarded-For).
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "")
        )

        # Duplicate check — block same email or same phone on this product.
        phone = (data.get("phone") or "").strip()[:32]
        if Sale.objects.filter(product=product, email__iexact=email).exists():
            return JsonResponse({
                "ok": False,
                "error": "Hai già effettuato la registrazione con questa email."
            }, status=400)
        if phone and Sale.objects.filter(product=product, phone=phone).exists():
            return JsonResponse({
                "ok": False,
                "error": "Hai già effettuato la registrazione con questo numero di telefono."
            }, status=400)

        sale = Sale.objects.create(
            product=product,
            firstname=(data.get("firstname") or "").strip()[:120],
            lastname=(data.get("lastname") or "").strip()[:120],
            email=email[:254],
            phone=(data.get("phone") or "").strip()[:32],
            country=(data.get("country") or "IT").strip().upper()[:8],
            notes=f"IP: {ip}" if ip else "",
        )

        # Mirror into Lead so the /leads/ pipeline sees it too.
        lead = None
        try:
            from apps.leads.models import Lead
            lead = Lead.objects.create(
                uniqueid=f"sale-{sale.pk}",
                firstname=sale.firstname,
                lastname=sale.lastname,
                email=sale.email,
                phone=sale.phone,
                country=sale.country,
                status="New",
                source=f"product-{product.slug}",
                payload={
                    "product_id": product.pk,
                    "product_slug": product.slug,
                    "product_name": product.name,
                    "sale_id": sale.pk,
                    "ip": ip,
                    **{k: v for k, v in data.items() if k != "csrfmiddlewaretoken"},
                },
            )
        except Exception:
            pass

        # Auto-dispatch lead to active push sources (ping-tree).
        if lead:
            try:
                from apps.leads.dispatch import dispatch
                from apps.leads.models import LeadSource
                sources = list(
                    LeadSource.objects.filter(is_active=True)
                    .order_by("priority", "name")
                )
                sources = [s for s in sources if s.can_push]
                if sources:
                    dispatch(lead, sources=sources, stop_on_success=True)
            except Exception:
                pass

        return JsonResponse({"ok": True, "sale_id": sale.pk,
                             "redirect": product.redirect_url or ""})


# ── Sales admin (staff) ─────────────────────────────────────────────────

class SaleListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Sale
    template_name = "products/sale_list.html"
    context_object_name = "sales"
    breadcrumb_title = "Vendite"
    paginate_by = 50

    def get_queryset(self):
        qs = Sale.objects.select_related("product")
        status = self.request.GET.get("status")
        if status in dict(Sale.STATUS_CHOICES):
            qs = qs.filter(status=status)
        product_slug = self.request.GET.get("product")
        if product_slug:
            qs = qs.filter(product__slug=product_slug)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_filter"] = self.request.GET.get("status", "")
        ctx["product_filter"] = self.request.GET.get("product", "")
        ctx["status_choices"] = Sale.STATUS_CHOICES
        ctx["products"] = Product.objects.filter(status="published").order_by("name")
        ctx["counts"] = {
            "all": Sale.objects.count(),
            "pending": Sale.objects.filter(status="pending").count(),
            "sold": Sale.objects.filter(status="sold").count(),
            "lost": Sale.objects.filter(status="lost").count(),
        }
        return ctx


class SaleUpdateStatusView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    """POST {status: sold|lost|pending} for a Sale. Calls the product's
    status_api_url if configured, stores the API response."""

    def post(self, request, pk):
        sale = get_object_or_404(Sale.objects.select_related("product"), pk=pk)
        new_status = request.POST.get("status", "")
        if new_status not in dict(Sale.STATUS_CHOICES):
            toast(request, LEVEL_ERROR, f"Stato non valido: {new_status}")
            return redirect("products:sale_list")

        sale.status = new_status
        if new_status == Sale.STATUS_SOLD:
            sale.sold_at = timezone.now()
        sale.save(update_fields=["status", "sold_at", "updated_at"])

        api_result = self._notify_external(sale)
        if api_result is not None:
            sale.api_response = api_result
            sale.save(update_fields=["api_response", "updated_at"])

        # Mirror status onto the Lead row created at submit time.
        try:
            from apps.leads.models import Lead
            Lead.objects.filter(uniqueid=f"sale-{sale.pk}").update(
                status=new_status,
                is_deposit=(new_status == Sale.STATUS_SOLD),
            )
        except Exception:
            pass

        toast(request, LEVEL_SUCCESS,
              f"Vendita #{sale.pk} → {sale.get_status_display()}.")
        return redirect("products:sale_list")

    @staticmethod
    def _notify_external(sale):
        url = (sale.product.status_api_url or "").strip()
        if not url:
            return None
        payload = {
            "sale_id": sale.pk,
            "product_id": sale.product.pk,
            "product_slug": sale.product.slug,
            "product_name": sale.product.name,
            "status": sale.status,
            "firstname": sale.firstname,
            "lastname": sale.lastname,
            "email": sale.email,
            "phone": sale.phone,
            "country": sale.country,
            "sold_at": sale.sold_at.isoformat() if sale.sold_at else None,
            "api_key": sale.product.status_api_key,
        }
        req = urllib.request.Request(
            url, method="POST",
            data=json.dumps(payload).encode("utf-8"),
        )
        req.add_header("Content-Type", "application/json")
        if sale.product.status_api_key:
            req.add_header("X-API-Key", sale.product.status_api_key)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")[:4000]
                return {"ok": True, "status_code": resp.status, "body": body}
        except urllib.error.HTTPError as e:
            return {"ok": False, "status_code": e.code,
                    "body": e.read().decode("utf-8", errors="replace")[:4000]}
        except Exception as e:
            return {"ok": False, "error": str(e)[:500]}
