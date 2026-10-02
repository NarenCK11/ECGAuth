"""Test harness. Tests run against a real MySQL database that is *separate* from the dev one.

TEST_DATABASE_URL (env or repo-root .env) must point at a database whose name ends in `_test`;
it is migrated with Alembic and emptied between tests.
"""
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _test_db_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL")
    env_file = REPO_ROOT / ".env"
    if not url and env_file.exists():
        m = re.search(r"^TEST_DATABASE_URL=(.+)$", env_file.read_text(), flags=re.M)
        url = m.group(1).strip() if m else None
    return url


TEST_DB_URL = _test_db_url()

# Must be set before `app.core.config` is first imported.
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123456789")
os.environ["ADMIN_USERNAME"] = "testadmin"
os.environ["ADMIN_PASSWORD"] = "testadmin-password-1"
os.environ["LOGIN_MAX_FAILURES"] = "5"
if TEST_DB_URL:
    assert re.search(r"/[^/?]*_test(\?|$)", TEST_DB_URL), "TEST_DATABASE_URL must name a *_test database"
    os.environ["DATABASE_URL"] = TEST_DB_URL

import sqlalchemy as sa  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

needs_db = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not configured")


@pytest.fixture(scope="session")
def db_engine():
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not configured")
    from app.core.database import get_engine

    engine = get_engine()
    with engine.begin() as c:  # start from a clean slate, then migrate with the real migrations
        c.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
        for (t,) in c.execute(sa.text("show tables")).all():
            c.execute(sa.text(f"drop table `{t}`"))
        c.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
    cfg = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    command.upgrade(cfg, "head")
    return engine


@pytest.fixture()
def db(db_engine):
    """A session on a freshly emptied database."""
    from app.core.database import get_sessionmaker

    with db_engine.begin() as c:
        c.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
        for t in ("audit_logs", "authentication_attempts", "analysis_profiles", "medical_records",
                  "ecg_enrollments", "users"):
            c.execute(sa.text(f"delete from {t}"))
        c.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
