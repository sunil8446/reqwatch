"""Shared fixture: a throwaway Postgres DSN (pgserver), or TEST_DATABASE_URL."""
from __future__ import annotations

import os

import pytest

pgserver = pytest.importorskip("pgserver")


@pytest.fixture(scope="module")
def pg_dsn(tmp_path_factory):
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        yield test_url
        return
    srv = pgserver.get_server(tmp_path_factory.mktemp("pg"))
    yield srv.get_uri()
    srv.cleanup()
