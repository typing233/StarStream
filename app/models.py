from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    libraries = relationship("Library", back_populates="owner", cascade="all, delete-orphan")


class Library(Base):
    __tablename__ = "libraries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    path = Column(String(500), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="libraries")
    media_items = relationship("MediaItem", back_populates="library", cascade="all, delete-orphan")


class MediaItem(Base):
    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id"), nullable=False)
    title = Column(String(255), nullable=False)
    year = Column(Integer, nullable=True)
    media_type = Column(String(20), nullable=False)  # video, audio, image, ebook
    file_path = Column(String(1000), nullable=False, unique=True)
    file_size = Column(Integer, default=0)
    duration = Column(Float, nullable=True)
    cover_path = Column(String(500), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    bitrate = Column(Integer, nullable=True)
    codec = Column(String(50), nullable=True)
    artist = Column(String(255), nullable=True)
    album = Column(String(255), nullable=True)
    audio_tracks = Column(Text, nullable=True)  # JSON list
    subtitle_tracks = Column(Text, nullable=True)  # JSON list
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    library = relationship("Library", back_populates="media_items")
