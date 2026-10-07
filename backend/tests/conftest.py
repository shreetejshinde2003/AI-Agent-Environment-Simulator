"""Explicit isolation for tests that exercise unauthenticated app startup."""
import hashlib
from pathlib import Path

import pytest

from app.storage.database import repository


@pytest.fixture
def isolated_startup_repository(tmp_path):
    # TestClient's lifespan initializes storage and runs recovery even when the request
    # is denied. Never let authentication-denial tests open an application DB.
    original = (repository.path, repository._engine, repository._engine_url)
    default_path = Path(repository.path) if repository.path and repository.path != ':memory:' else None

    def fingerprint():
        return hashlib.sha256(default_path.read_bytes()).hexdigest() if default_path and default_path.exists() else None

    before = fingerprint()
    repository.path = str(tmp_path / 'startup.db')
    repository._engine = repository._engine_url = None
    try:
        yield repository
    finally:
        if repository._engine is not None:
            repository._engine.dispose()
        repository.path, repository._engine, repository._engine_url = original
        assert fingerprint() == before, 'Authentication-denial test touched the default application database'
