from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import Annotated, BinaryIO
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class, Lesson
from app.db import get_db
from app.deps import class_role, require_class_lecturer, require_class_member, require_user
from app.errors import APIError
from app.ingest import queue
from app.materials.models import Material, MaterialVersion, Visibility
from app.materials.policy import can_read_version
from app.materials.schemas import (
    LecturerMaterial,
    StudentMaterial,
    UploadResult,
    VersionDetail,
    VersionSummary,
)
from app.materials.service import lecturer_material, save_upload, validate_file
from app.materials.storage import LocalStorage, Storage

router = APIRouter(prefix="/api", tags=["materials"])


def get_storage() -> Storage:
    return LocalStorage()


@router.post("/classes/{class_id}/materials", status_code=201)
def create_material(
    file: UploadFile,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    classroom: Class = Depends(require_class_lecturer),
    lesson_id: Annotated[UUID | None, Form()] = None,
    visibility: Annotated[Visibility, Form()] = "students",
    source_note: Annotated[str | None, Form()] = None,
    license_note: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    storage: Storage = Depends(get_storage),
) -> UploadResult:
    if not title.strip():
        raise APIError(422, "validation_error", "Tiêu đề không được để trống.")
    if lesson_id is not None:
        lesson = db.get(Lesson, lesson_id)
        if lesson is None or lesson.class_id != classroom.id:
            raise HTTPException(404)
    validated = validate_file(file)
    material = Material(
        class_id=classroom.id,
        lesson_id=lesson_id,
        title=title.strip(),
        kind=validated.kind,
        visibility=visibility,
        source_note=source_note,
        license_note=license_note,
    )
    return save_upload(db, user, material, validated, storage, new_material=True)


@router.post("/materials/{material_id}/versions", status_code=201)
def create_version(
    material_id: UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    storage: Storage = Depends(get_storage),
) -> UploadResult:
    material = lecturer_material(db, user, material_id)
    validated = validate_file(file)
    if validated.kind != material.kind:
        raise APIError(422, "material_kind_mismatch", "Loại tệp phải trùng với học liệu.")
    return save_upload(db, user, material, validated, storage, new_material=False)


@router.get("/classes/{class_id}/materials")
def list_materials(
    classroom: Class = Depends(require_class_member),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[LecturerMaterial] | list[StudentMaterial]:
    if class_role(db, user, classroom.id) == "lecturer":
        result = []
        for material in db.scalars(
            select(Material)
            .where(Material.class_id == classroom.id)
            .order_by(Material.created_at, Material.id)
        ):
            item = LecturerMaterial.model_validate(material)
            item.versions = [
                VersionSummary.model_validate(version)
                for version in db.scalars(
                    select(MaterialVersion)
                    .where(MaterialVersion.material_id == material.id)
                    .order_by(MaterialVersion.version_no)
                )
            ]
            result.append(item)
        return result
    rows = db.execute(
        select(Material, MaterialVersion)
        .join(
            MaterialVersion,
            (MaterialVersion.id == Material.active_version_id)
            & (MaterialVersion.material_id == Material.id),
        )
        .where(
            Material.class_id == classroom.id,
            Material.visibility == "students",
            MaterialVersion.status == "published",
        )
        .order_by(Material.created_at, Material.id)
    )
    return [
        StudentMaterial(
            id=material.id,
            title=material.title,
            lesson_id=material.lesson_id,
            kind=material.kind,
            active_version_id=material.active_version_id,
            page_count=version.page_count,
            source_note=material.source_note,
            license_note=material.license_note,
        )
        for material, version in rows
    ]


def find_version(db: Session, version_id: UUID) -> MaterialVersion:
    version = db.get(MaterialVersion, version_id)
    if version is None:
        raise HTTPException(404)
    return version


@router.get("/material-versions/{version_id}")
def version_status(
    version_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> VersionDetail:
    version = find_version(db, version_id)
    lecturer_material(db, user, version.material_id)
    return VersionDetail.model_validate(version)


@router.post("/material-versions/{version_id}/reprocess")
def reprocess_version(
    version_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> VersionDetail:
    version = find_version(db, version_id)
    lecturer_material(db, user, version.material_id)
    changed = db.scalar(
        update(MaterialVersion)
        .where(MaterialVersion.id == version_id, MaterialVersion.status == "failed")
        .values(status="uploaded", error=None, processing_started_at=None)
        .returning(MaterialVersion.id)
    )
    if changed is None:
        db.rollback()
        raise APIError(409, "invalid_state", "Chỉ có thể xử lý lại học liệu bị lỗi.")
    db.commit()
    db.refresh(version)
    result = VersionDetail.model_validate(version)
    queue.enqueue_ingest(version_id)
    return result


def stream_file(stream: BinaryIO) -> Iterator[bytes]:
    with stream:
        while block := stream.read(64 * 1024):
            yield block


@router.get("/material-versions/{version_id}/file")
def read_file(
    version_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    storage: Storage = Depends(get_storage),
) -> StreamingResponse:
    version = find_version(db, version_id)
    if not can_read_version(db, user, version):
        raise HTTPException(404)
    try:
        stream = storage.open(version.storage_key)
    except FileNotFoundError:
        raise HTTPException(404) from None
    extension = PurePosixPath(version.storage_key).suffix
    media_type = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}[
        extension
    ]
    filename = (version.original_filename or f"material{extension}").replace("\\", "/")
    filename = filename.rsplit("/", 1)[-1]
    filename = "".join(char for char in filename if ord(char) >= 32 and ord(char) != 127)
    return StreamingResponse(
        stream_file(stream),
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename, safe='')}",
        },
    )
