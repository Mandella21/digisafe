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
