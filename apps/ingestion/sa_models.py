"""
SQLAlchemy models for heavy database operations.
Used alongside Django ORM for complex queries and bulk operations.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text,
    UniqueConstraint, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.pool import QueuePool
from datetime import datetime
import os

Base = declarative_base()


class FloatSA(Base):
    """SQLAlchemy model for ARGO floats."""
    __tablename__ = 'floats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_number = Column(String(20), unique=True, nullable=False, index=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    profiles = relationship("ProfileSA", back_populates="float", cascade="all, delete-orphan")


class ProfileSA(Base):
    """SQLAlchemy model for measurement profiles."""
    __tablename__ = 'profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    float_id = Column(Integer, ForeignKey('floats.id', ondelete='CASCADE'), nullable=False, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    profile_time = Column(DateTime, nullable=False, index=True)
    
    float = relationship("FloatSA", back_populates="profiles")
    measurements = relationship("MeasurementSA", back_populates="profile", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('float_id', 'profile_time', name='uq_float_profile_time'),
        Index('ix_profiles_lat_lon', 'latitude', 'longitude'),
        Index('ix_profiles_float_time', 'float_id', 'profile_time'),
    )


class MeasurementSA(Base):
    """SQLAlchemy model for individual measurements."""
    __tablename__ = 'measurements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    pressure = Column(Float, nullable=True, index=True)
    temperature = Column(Float, nullable=True)
    salinity = Column(Float, nullable=True)
    
    profile = relationship("ProfileSA", back_populates="measurements")


class ProcessedFileSA(Base):
    """SQLAlchemy model for tracking processed files."""
    __tablename__ = 'processed_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(500), unique=True, nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow, index=True)
    records_inserted = Column(Integer, default=0)
    status = Column(String(20), default='success')
    error_message = Column(Text, nullable=True)


def get_engine(database_url: str = None):
    """
    Create SQLAlchemy engine with connection pooling.
    
    Args:
        database_url: PostgreSQL connection string
        
    Returns:
        SQLAlchemy engine
    """
    if database_url is None:
        database_url = os.getenv('DATABASE_URL', '')
    
    if not database_url:
        raise ValueError("DATABASE_URL is not configured")
    
    # Ensure SSL is required for Neon
    if 'sslmode' not in database_url:
        database_url += '?sslmode=require' if '?' not in database_url else '&sslmode=require'
    
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True,
        echo=False,
    )
    
    return engine


def get_session(engine=None):
    """
    Create a new database session.
    
    Args:
        engine: SQLAlchemy engine (optional)
        
    Returns:
        SQLAlchemy session
    """
    if engine is None:
        engine = get_engine()
    
    Session = sessionmaker(bind=engine)
    return Session()


def create_tables(engine=None):
    """
    Create all tables in the database.
    
    Args:
        engine: SQLAlchemy engine (optional)
    """
    if engine is None:
        engine = get_engine()
    
    Base.metadata.create_all(engine)
