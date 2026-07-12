from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

# Connection string configured for XAMPP (User: root, Password: empty)
DATABASE_URL = "mysql+pymysql://root:@localhost:3306/campus_helpdesk"

# Create the database engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create a session factory for database operations
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for our ORM model mapping
Base = declarative_base()

# Dependency to inject the database session into FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ORM Model mapping to your 'tickets' table for Developers 2 & 3
class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    category = Column(String(50), nullable=False)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="Medium")
    status = Column(String(20), default="Open")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)