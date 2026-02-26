import pytest
import sqlite3
from it_job_aggregator.db import Database
from it_job_aggregator.models import Job


@pytest.fixture
def db():
    """Fixture to provide an in-memory database for testing."""
    with Database(db_path=":memory:") as test_db:
        yield test_db


def test_init_db(db):
    """Test that the table is created correctly."""
    conn = db.connection
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
    assert cursor.fetchone() is not None


def test_save_job_success(db):
    """Test saving a valid job."""
    job = Job(
        title="Software Engineer",
        company="Acme Inc",
        link="https://example.com/acme",
        description="Great job.",
        source="website",
    )

    assert db.save_job(job) is True

    # Verify it was actually saved
    cursor = db.connection.cursor()
    cursor.execute("SELECT title, link FROM jobs WHERE link = ?", (str(job.link),))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "Software Engineer"
    assert row[1] == str(job.link)


def test_save_job_duplicate_link(db):
    """Test that saving a job with an existing link returns False."""
    job1 = Job(
        title="Software Engineer",
        company="Acme Inc",
        link="https://example.com/acme",
        description="Great job.",
        source="website",
    )

    job2 = Job(
        title="Different Title",
        company="Different Company",
        link="https://example.com/acme",  # Same link!
        description="Different description.",
        source="telegram",
    )

    # First save should succeed
    assert db.save_job(job1) is True

    # Second save with same link should return False (duplicate)
    assert db.save_job(job2) is False

    # Verify only one job exists in the DB
    cursor = db.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    count = cursor.fetchone()[0]
    assert count == 1


# --- New tests ---


def test_context_manager_closes_connection():
    """Test that the context manager properly closes the connection on exit."""
    with Database(db_path=":memory:") as test_db:
        conn = test_db.connection
        assert conn is not None

    # After exiting the context manager, _conn should be None
    assert test_db._conn is None


def test_close_method():
    """Test that close() sets _conn to None and can be called safely."""
    test_db = Database(db_path=":memory:")
    assert test_db._conn is not None

    test_db.close()
    assert test_db._conn is None

    # Calling close() again should not raise
    test_db.close()
    assert test_db._conn is None


def test_save_job_with_none_company(db):
    """Test that a job with company=None is saved correctly."""
    job = Job(
        title="QA Engineer",
        link="https://example.com/qa",
        description="Join our team.",
        source="telegram",
    )
    assert job.company is None
    assert db.save_job(job) is True

    cursor = db.connection.cursor()
    cursor.execute("SELECT title, company FROM jobs WHERE link = ?", (str(job.link),))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "QA Engineer"
    assert row[1] is None  # NULL in SQLite


def test_created_at_auto_timestamp(db):
    """Test that created_at is automatically set when a job is saved."""
    job = Job(
        title="DevOps Engineer",
        company="Cloud Co",
        link="https://example.com/devops",
        description="Cloud stuff.",
        source="website",
    )
    db.save_job(job)

    cursor = db.connection.cursor()
    cursor.execute("SELECT created_at FROM jobs WHERE link = ?", (str(job.link),))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] is not None  # Should have a timestamp
    # Verify it looks like a timestamp (YYYY-MM-DD HH:MM:SS)
    assert len(row[0]) >= 19


def test_init_db_called_twice_is_safe(db):
    """Test that calling init_db() a second time doesn't destroy existing data."""
    job = Job(
        title="Existing Job",
        company="Corp",
        link="https://example.com/existing",
        description="Already here.",
        source="website",
    )
    db.save_job(job)

    # Call init_db again (CREATE TABLE IF NOT EXISTS should be safe)
    db.init_db()

    cursor = db.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    count = cursor.fetchone()[0]
    assert count == 1  # Data still intact


def test_save_job_stores_all_fields(db):
    """Test that all fields are correctly stored and retrievable."""
    job = Job(
        title="Full Stack Developer",
        company="Startup Inc",
        link="https://example.com/fullstack",
        description="React + Node.js position.",
        source="Telegram (@channel)",
    )
    db.save_job(job)

    cursor = db.connection.cursor()
    cursor.execute(
        "SELECT title, company, link, description, source FROM jobs WHERE link = ?",
        (str(job.link),),
    )
    row = cursor.fetchone()
    assert row[0] == "Full Stack Developer"
    assert row[1] == "Startup Inc"
    assert row[2] == str(job.link)
    assert row[3] == "React + Node.js position."
    assert row[4] == "Telegram (@channel)"
