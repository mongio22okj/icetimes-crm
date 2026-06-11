from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from .forms import ProductForm
from .models import Category, Product


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
