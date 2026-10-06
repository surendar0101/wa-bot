from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./finance_consultation.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import Customer, Conversation, Appointment, Message, FormSubmission  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite():
    """Add new columns to existing SQLite DBs without full reset."""
    if not str(engine.url).startswith("sqlite"):
        return
    from sqlalchemy import text

    migrations = [
        "ALTER TABLE customers ADD COLUMN existing_investment_types VARCHAR(200)",
        "ALTER TABLE customers ADD COLUMN investment_details TEXT",
        "ALTER TABLE appointments ADD COLUMN meet_link VARCHAR(500)",
        "ALTER TABLE appointments ADD COLUMN calendar_event_id VARCHAR(200)",
        "ALTER TABLE appointments ADD COLUMN calendar_html_link VARCHAR(500)",
        "ALTER TABLE customers ADD COLUMN intake_source VARCHAR(50)",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
