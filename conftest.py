"""Project-wide pytest configuration.

Resets the active language to English before each test so tests that
poke at translated lazy strings (e.g. apps/core/tests/test_navigation.py)
aren't affected by other tests' locale activation.
"""
import pytest


@pytest.fixture(autouse=True)
def _reset_language_to_english():
    from django.utils import translation
    translation.activate("en")
    yield
    translation.deactivate_all()
