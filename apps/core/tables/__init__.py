"""Reusable HTMX-driven datatable system.

Public API:

    from apps.core.tables import TableView, TableConfig, Column, Filter, BulkAction

A list view opts in by setting `table_config = TableConfig(...)` and inheriting
from `TableView` instead of `ListView`. Sort, filter, paginate, search, column
visibility, bulk actions, and exports come for free. See the spec at
docs/superpowers/specs/2026-04-29-phase11-datatable-design.md for details.
"""
from apps.core.tables.config import (
    BulkAction,
    Column,
    Filter,
    TableConfig,
)
from apps.core.tables.views import TableView

__all__ = ["BulkAction", "Column", "Filter", "TableConfig", "TableView"]
