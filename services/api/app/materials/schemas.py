from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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


class UploadResult(BaseModel):
    material: LecturerMaterial
    version: VersionDetail
