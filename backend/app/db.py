import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DB_USER = os.getenv("KPANEL_DB_USER", "kpanel")
DB_PASSWORD = os.getenv("KPANEL_DB_PASSWORD", "kpanel")
DB_HOST = os.getenv("KPANEL_DB_HOST", "mariadb")
DB_PORT = int(os.getenv("KPANEL_DB_PORT", "3306"))
DB_NAME = os.getenv("KPANEL_DB_NAME", "kpanel")

DATABASE_URL = os.getenv(
    "KPANEL_DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
