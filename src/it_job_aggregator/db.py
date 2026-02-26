import logging
import sqlite3
from types import TracebackType

from it_job_aggregator.models import Job

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database for storing and deduplicating job postings.
    Uses a single persistent connection for both file-based and in-memory databases.
    Supports context manager protocol for proper resource cleanup.
    """

    def __init__(self, db_path: str = "jobs.db") -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = sqlite3.connect(db_path)
        self.init_db()

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the persistent database connection."""
        if self._conn is None:
            raise RuntimeError("Database connection is closed")
        return self._conn

    def init_db(self) -> None:
        """Create the jobs table if it doesn't exist."""
        cursor = self.connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT,
                link TEXT NOT NULL UNIQUE,
                description TEXT,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def save_job(self, job: Job) -> bool:
        """
        Attempt to save a job to the database.
        Returns True if saved successfully, False if it was a duplicate (based on the link).
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (title, company, link, description, source)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    job.title,
                    job.company,
                    str(job.link),  # HttpUrl must be cast to string for sqlite
                    job.description,
                    job.source,
                ),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            # The link already exists in the database
            logger.debug(f"Duplicate job skipped: {job.link}")
            return False
        except Exception as e:
            logger.error(f"Error saving job {job.link}: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
