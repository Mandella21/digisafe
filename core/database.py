from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings


def _normalise_database_url(url: str) -> str:
    """Make a hosting provider's DATABASE_URL usable by SQLAlchemy.

    Render, Heroku and several others hand out connection strings beginning
    'postgres://'. SQLAlchemy removed that alias in 1.4 and raises
    NoSuchModuleError on it, so a deployment that is otherwise correct fails at
    import with an error naming a dialect nobody wrote. Rewriting it here means
    the value can be pasted from the dashboard exactly as given.

    The driver is pinned to psycopg (v3) because that is what requirements.txt
    installs; left unqualified, SQLAlchemy looks for psycopg2 and fails.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalise_database_url(settings.DATABASE_URL)
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# check_same_thread is a SQLite-only concept, and passing it to any other
# driver is an immediate connection error.
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine_kwargs = {"connect_args": connect_args}
if not IS_SQLITE:
    # Managed Postgres instances drop idle connections, and free tiers are the
    # most aggressive about it. Without pre-ping the first request after a quiet
    # period fails on a connection the pool still believes is alive; with it,
    # that connection is quietly discarded and replaced.
    engine_kwargs["pool_pre_ping"] = True
    # Free tiers also cap total connections tightly, so keep the pool small
    # enough that one web service cannot exhaust it on its own.
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 5
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema():
    """Additive, idempotent schema top-up for databases that already exist.

    SQLAlchemy's create_all() creates missing TABLES but never adds a column to
    a table that already exists. A developer or examiner running an older
    database would therefore hit "no such column" after pulling an update. This
    adds any missing nullable columns in place, so an existing database keeps
    its evidence records instead of having to be deleted and rebuilt.
    """
    from sqlalchemy import inspect, text

    # Column types are written per dialect rather than once, because the two
    # disagree on details that matter here: SQLite has no boolean type and
    # accepts 0/1, Postgres has a real one and rejects 0; SQLite stores bytes
    # in a BLOB, Postgres in BYTEA.
    dialect = "sqlite" if IS_SQLITE else "postgresql"
    BOOL_FALSE = "BOOLEAN DEFAULT 0" if IS_SQLITE else "BOOLEAN DEFAULT FALSE"
    BLOB = "BLOB" if IS_SQLITE else "BYTEA"
    TIMESTAMP = "DATETIME" if IS_SQLITE else "TIMESTAMP"

    additive_columns = {
        "ml_classifications": {
            "detected_categories": "TEXT",
        },
        "users": {
            "is_verified": BOOL_FALSE,
            "verification_code": "VARCHAR(10)",
            "verification_token": "VARCHAR(64)",
            "verification_sent_at": TIMESTAMP,
            "verification_expires_at": TIMESTAMP,
            "verification_attempts": "INTEGER DEFAULT 0",
            "verified_at": TIMESTAMP,
        },
        "evidence": {
            "file_data": BLOB,
            "file_name": "VARCHAR(255)",
            "file_mime": "VARCHAR(120)",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table, columns in additive_columns.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for column, column_type in columns.items():
                if column not in present:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                    )
                    print(f"Schema updated: added {table}.{column} ({dialect})")

    _run_once_migrations()


def _run_once_migrations():
    """Data fix-ups that must happen exactly once in a database's lifetime.

    Column top-ups above are safe to re-evaluate every boot, because "does this
    column exist" answers itself. A data migration cannot be re-derived that
    way: re-running one would quietly overwrite whatever has happened since. So
    each is recorded by name in schema_migrations and skipped ever after.

    On a brand-new database these are no-ops - create_all() has already built
    every column and no rows exist yet - which is why they can run
    unconditionally rather than trying to detect an "old" database.
    """
    from sqlalchemy import text

    true_value = "1" if IS_SQLITE else "TRUE"
    false_value = "0" if IS_SQLITE else "FALSE"

    migrations = [
        (
            "2026-09-users-grandfather-pre-verification-accounts",
            # Accounts created before email verification existed were made under
            # rules that never asked for it. Leaving them at the column default
            # would lock every one of them out on the next start - including, on
            # a developer's machine, the account holding real evidence records.
            f"UPDATE users SET is_verified = {true_value}, verified_at = CURRENT_TIMESTAMP "
            f"WHERE is_verified = {false_value} OR is_verified IS NULL",
        ),
    ]

    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  name VARCHAR(150) PRIMARY KEY,"
            "  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        applied = {
            row[0] for row in connection.execute(text("SELECT name FROM schema_migrations"))
        }
        for name, statement in migrations:
            if name in applied:
                continue
            result = connection.execute(text(statement))
            connection.execute(
                text("INSERT INTO schema_migrations (name) VALUES (:name)"),
                {"name": name},
            )
            print(f"Migration applied: {name} ({result.rowcount} row(s) affected)")
