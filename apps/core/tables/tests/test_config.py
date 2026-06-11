"""Pure dataclass tests — no DB, no Django app loading required."""
from apps.core.tables.config import (
    BulkAction,
    Column,
    Filter,
    TableConfig,
)


def _basic_config() -> TableConfig:
    return TableConfig(
        key="customers",
        columns=(
            Column("name", "Name", searchable=True, pinned=True),
            Column("email", "Email", searchable=True),
            Column("status", "Status", filter=Filter("select",
                                                    choices=(("a", "Active"), ("p", "Pending")))),
            Column("created_at", "Created", filter=Filter("daterange"), priority=2),
            Column("notes", "Notes", sortable=False, priority=3),
        ),
        bulk_actions=(
            BulkAction("archive", "Archive"),
            BulkAction("delete", "Delete", destructive=True,
                       confirm_text="Delete {n}? Cannot be undone."),
        ),
    )


def test_column_defaults():
    c = Column("name", "Name")
    assert c.sortable is True
    assert c.searchable is False
    assert c.filter is None
    assert c.priority == 1
    assert c.pinned is False


def test_filter_resolved_choices_handles_callable():
    f = Filter("select", choices=lambda: (("x", "X"), ("y", "Y")))
    assert f.resolved_choices() == (("x", "X"), ("y", "Y"))


def test_filter_resolved_choices_handles_static_tuple():
    f = Filter("select", choices=(("x", "X"),))
    assert f.resolved_choices() == (("x", "X"),)


def test_filter_resolved_choices_empty_default():
    assert Filter("text").resolved_choices() == ()


def test_table_config_helpers():
    config = _basic_config()
    assert config.column_keys() == ("name", "email", "status", "created_at", "notes")
    # All columns sortable except `notes`
    assert config.sortable_column_keys() == {"name", "email", "status", "created_at"}
    assert config.searchable_column_keys() == {"name", "email"}
    assert config.column("status").label == "Status"
    assert config.column("nope") is None


def test_table_config_default_pagination_is_page_numbered():
    assert _basic_config().pagination == "page"


def test_table_config_defaults_to_page_size_25():
    assert _basic_config().page_size == 25


def test_table_config_default_exports_all_three_formats():
    assert set(_basic_config().exports) == {"csv", "xlsx", "pdf"}


def test_bulk_action_defaults():
    a = BulkAction("delete", "Delete")
    assert a.destructive is False
    assert a.confirm_text is None
    assert a.icon == ""


def test_table_config_is_immutable():
    """frozen=True: a TableConfig declared on a view class can't be mutated
    by accident at request time."""
    config = _basic_config()
    try:
        config.page_size = 50  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("TableConfig should be frozen")
