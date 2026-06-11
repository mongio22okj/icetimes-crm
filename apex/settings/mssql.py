"""
Local development settings for Microsoft SQL Server.

Use this when you want to develop against SQL Server locally instead of
SQLite (the dev default). Production uses apex.settings.prod with a
DATABASE_URL of the form `mssql://user:pass@host:1433/dbname`.

Prerequisites:
  1. Install the mssql extra:        uv sync --extra mssql
  2. Install Microsoft ODBC Driver 18 (see README "SQL Server" section).
  3. Have a SQL Server instance reachable at MSSQL_HOST:MSSQL_PORT with
     a database named in MSSQL_DB.

Run with:
  DJANGO_SETTINGS_MODULE=apex.settings.mssql uv run python manage.py migrate
"""

import os

from .dev import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.environ.get("MSSQL_DB", "apex"),
        "USER": os.environ.get("MSSQL_USER", "sa"),
        "PASSWORD": os.environ.get("MSSQL_PASSWORD", "Apex_Test_123!"),
        "HOST": os.environ.get("MSSQL_HOST", "localhost"),
        "PORT": os.environ.get("MSSQL_PORT", "1433"),
        "OPTIONS": {
            "driver": os.environ.get("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server"),
            # Local dev typically uses a self-signed cert (e.g. the docker
            # image) so cert validation is skipped. In production, manage
            # the cert properly and remove this.
            "extra_params": "TrustServerCertificate=yes",
        },
    }
}
