import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool

from config.settings import settings
from database.models import Base

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._init_engine()

    def _init_engine(self):
        try:
            self.engine = create_engine(
                settings.DATABASE_URL,
                echo=settings.DB_ECHO,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
            self.SessionLocal = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine
                )
            )
            logger.info("Database engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise

    def get_session(self):
        return self.SessionLocal()

    def close_session(self, session):
        if session:
            session.close()

    def dispose_engine(self):
        if self.engine:
            self.engine.dispose()
            logger.info("Database engine disposed")


db = Database()
