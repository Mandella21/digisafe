from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings

connect_args = {'check_same_thread': False} if 'sqlite' in settings.DATABASE_URL else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema():
    """Additive, idempotent schema top-up for existing SQLite databases.

    SQLAlchemy's create_all() creates missing TABLES but never adds a column to
    a table that already exists. A developer or examiner running an older
    digisafe.db would therefore hit "no such column" after pulling an update.
    This adds any missing nullable columns in place, so an existing database
    keeps its evidence records instead of having to be deleted and re-seeded.
    """
    from sqlalchemy import inspect, text

    additive_columns = {
        "ml_classifications": {
            "detected_categories": "TEXT",
        },
        "users": {
            "is_verified": "BOOLEAN DEFAULT 0",
            "verification_code": "VARCHAR(10)",
            "verification_token": "VARCHAR(64)",
            "verification_sent_at": "DATETIME",
            "verification_expires_at": "DATETIME",
            "verification_attempts": "INTEGER DEFAULT 0",
            "verified_at": "DATETIME",
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
                    print(f"Schema updated: added {table}.{column}")

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

    migrations = [
        (
            "2026-09-users-grandfather-pre-verification-accounts",
            # Accounts created before email verification existed were made under
            # rules that never asked for it. Leaving them at the column default
            # would lock every one of them out on the next start - including, on
            # a developer's machine, the account holding real evidence records.
            "UPDATE users SET is_verified = 1, verified_at = CURRENT_TIMESTAMP "
            "WHERE is_verified = 0 OR is_verified IS NULL",
        ),
    ]

    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  name VARCHAR(150) PRIMARY KEY,"
            "  applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
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
