import sqlite3

import pytest

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
        source="Jobs.ps",
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
        source="Jobs.ps",
    )

    job2 = Job(
        title="Different Title",
        company="Different Company",
        link="https://example.com/acme",  # Same link!
        description="Different description.",
        source="Jobs.ps",
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
        source="Jobs.ps",
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
        source="Jobs.ps",
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
        source="Jobs.ps",
    )
    db.save_job(job)

    # Call init_db again (CREATE TABLE IF NOT EXISTS should be safe)
    db.init_db()

    cursor = db.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    count = cursor.fetchone()[0]
    assert count == 1  # Data still intact


def test_save_job_stores_all_fields(db):
    """Test that all fields including new metadata fields are correctly stored."""
    job = Job(
        title="Full Stack Developer",
        company="Startup Inc",
        link="https://example.com/fullstack",
        description="React + Node.js position.",
        source="Jobs.ps",
        position_level="Mid-Level",
        location="Ramallah",
        deadline="2026-03-24",
        experience="3 Years",
        posted_date="24, Feb",
    )
    db.save_job(job)

    cursor = db.connection.cursor()
    cursor.execute(
        """SELECT title, company, link, description, source,
                  position_level, location, deadline, experience, posted_date
           FROM jobs WHERE link = ?""",
        (str(job.link),),
    )
    row = cursor.fetchone()
    assert row[0] == "Full Stack Developer"
    assert row[1] == "Startup Inc"
    assert row[2] == str(job.link)
    assert row[3] == "React + Node.js position."
    assert row[4] == "Jobs.ps"
    assert row[5] == "Mid-Level"
    assert row[6] == "Ramallah"
    assert row[7] == "2026-03-24"
    assert row[8] == "3 Years"
    assert row[9] == "24, Feb"


def test_save_job_with_null_metadata_fields(db):
    """Test that jobs without optional metadata fields store NULL in the database."""
    job = Job(
        title="Backend Dev",
        link="https://example.com/backend",
        description="Python backend.",
        source="Jobs.ps",
    )
    db.save_job(job)

    cursor = db.connection.cursor()
    cursor.execute(
        """SELECT position_level, location, deadline, experience, posted_date
           FROM jobs WHERE link = ?""",
        (str(job.link),),
    )
    row = cursor.fetchone()
    assert row[0] is None
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None
    assert row[4] is None


def test_migrate_add_columns_on_old_schema():
    """Test that migration adds new columns to a database with the old schema."""
    # Create a database with the old schema (no metadata columns)
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            link TEXT NOT NULL UNIQUE,
            description TEXT,
            source TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Insert a job using the old schema
    conn.execute(
        "INSERT INTO jobs (title, company, link, description, source) VALUES (?, ?, ?, ?, ?)",
        ("Old Job", "Old Corp", "https://example.com/old", "Old desc.", "Jobs.ps"),
    )
    conn.commit()

    # Now create a Database instance that should run migration
    db = Database.__new__(Database)
    db.db_path = ":memory:"
    db._conn = conn
    db.init_db()

    # Verify new columns exist
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(jobs)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "position_level" in columns
    assert "location" in columns
    assert "deadline" in columns
    assert "experience" in columns
    assert "posted_date" in columns

    # Verify old data is still intact
    cursor.execute("SELECT title FROM jobs WHERE link = ?", ("https://example.com/old",))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "Old Job"

    # Verify we can save a new job with the new fields
    job = Job(
        title="New Job",
        link="https://example.com/new",
        description="New desc.",
        source="Jobs.ps",
        position_level="Senior",
        location="Ramallah",
    )
    assert db.save_job(job) is True

    cursor.execute(
        "SELECT position_level, location FROM jobs WHERE link = ?",
        (str(job.link),),
    )
    row = cursor.fetchone()
    assert row[0] == "Senior"
    assert row[1] == "Ramallah"

    conn.close()


def test_schema_has_new_columns(db):
    """Test that a freshly created database has all new metadata columns."""
    cursor = db.connection.cursor()
    cursor.execute("PRAGMA table_info(jobs)")
    columns = {row[1] for row in cursor.fetchall()}

    expected = {
        "id",
        "title",
        "company",
        "link",
        "description",
        "source",
        "position_level",
        "location",
        "deadline",
        "experience",
        "posted_date",
        "created_at",
    }
    assert columns == expected
