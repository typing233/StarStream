from pydantic import BaseModel
from typing import Generic, TypeVar
from datetime import datetime

T = TypeVar("T")


class ErrorResponse(BaseModel):
    detail: str


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    total_pages: int


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class MediaResponse(BaseModel):
    id: int
    title: str
    media_type: str
    year: int | None
    duration: float | None
    cover_path: str | None
    file_size: int | None
    metadata_json: dict | None
    library_id: int

    class Config:
        from_attributes = True


class PlayHistoryResponse(BaseModel):
    id: int
    media_id: int
    media_title: str | None = None
    media_type: str | None = None
    started_at: datetime | None = None
    duration_watched: float = 0
    completed: int = 0

    class Config:
        from_attributes = True


class ActivityLogResponse(BaseModel):
    id: int
    user_id: int | None
    username: str | None = None
    action: str
    details_json: dict | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
