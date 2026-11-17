from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.materials.models import MaterialKind, VersionStatus, Visibility


class StudentMaterial(BaseModel):
    id: UUID
    title: str
    lesson_id: UUID | None
    kind: MaterialKind
    active_version_id: UUID | None
    page_count: int | None
    source_note: str | None
    license_note: str | None


class VersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_no: int
    status: VersionStatus
    created_at: datetime
    size_bytes: int | None
    error: str | None


class VersionDetail(VersionSummary):
    material_id: UUID
    original_filename: str | None
    checksum_sha256: str
    page_count: int | None
    quality_report: dict[str, Any] | None
    created_by: UUID


class LecturerMaterial(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    class_id: UUID
    title: str
    lesson_id: UUID | None
    kind: MaterialKind
    visibility: Visibility
    active_version_id: UUID | None
    source_note: str | None
    license_note: str | None
    versions: list[VersionSummary] = []
    quality_report: dict[str, Any] | None = None


class UploadResult(BaseModel):
    material: LecturerMaterial
    version: VersionDetail


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    visibility: Visibility | None = None
    lesson_id: UUID | None = None

    @field_validator("title", "visibility", mode="before")
    @classmethod
    def nonempty(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("Giá trị không được để trống.")
        return value.strip() if isinstance(value, str) else value


class PageChunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ordinal: int
    kind: str
    char_start: int
    char_end: int


class PageText(BaseModel):
    page_index: int
    page_label: str
    text: str
    chunks: list[PageChunk]
