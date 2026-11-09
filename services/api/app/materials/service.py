import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, User
from app.deps import require_class_lecturer, require_class_member
from app.errors import APIError
from app.ingest import queue
from app.materials.models import Material, MaterialKind, MaterialVersion
from app.materials.schemas import LecturerMaterial, UploadResult, VersionDetail
from app.materials.storage import Storage


class UploadSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DUT_", extra="ignore")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)


@dataclass(frozen=True)
class ValidatedFile:
    filename: str
    extension: str
    kind: MaterialKind
    data: bytes
    checksum: str


def validate_file(upload: UploadFile) -> ValidatedFile:
    filename = upload.filename or ""
    if (
        not filename
        or any(char in filename for char in ("/", "\\", ":"))
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise APIError(422, "invalid_filename", "Tên tệp không hợp lệ.")
    extension = PurePosixPath(filename).suffix.lower().lstrip(".")
    if extension not in {"pdf", "txt", "md"}:
        raise APIError(415, "unsupported_media_type", "Chỉ hỗ trợ PDF, TXT hoặc MD.")
    limit = UploadSettings().max_upload_bytes
    data = bytearray()
    while block := upload.file.read(min(64 * 1024, limit + 1 - len(data))):
        data.extend(block)
        if len(data) > limit:
            raise APIError(413, "file_too_large", "Tệp vượt quá dung lượng cho phép.")
    if extension == "pdf":
        if not data.startswith(b"%PDF-"):
            raise APIError(415, "unsupported_media_type", "Tệp PDF không hợp lệ.")
    else:
        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise APIError(
                415, "unsupported_media_type", "Tệp văn bản phải có mã hóa UTF-8."
            ) from None
    return ValidatedFile(
        filename,
        extension,
        "pdf" if extension == "pdf" else "text",
        bytes(data),
        hashlib.sha256(data).hexdigest(),
    )


def lecturer_material(db: Session, user: User, material_id: UUID) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404)
    classroom = require_class_member(material.class_id, db, user)
    require_class_lecturer(classroom, db, user)
    return material


def save_upload(
    db: Session,
    user: User,
    material: Material,
    file: ValidatedFile,
    storage: Storage,
    *,
    new_material: bool,
) -> UploadResult:
    if new_material:
        material.id = uuid4()
        db.add(material)
        db.flush()
        number = 1
    else:
        # Serialize version allocation on the parent, including when there are no versions.
        db.execute(
            select(Material).where(Material.id == material.id).with_for_update()
        ).scalar_one()
        number = (
            db.scalar(
                select(func.max(MaterialVersion.version_no)).where(
                    MaterialVersion.material_id == material.id
                )
            )
            or 0
        ) + 1
    version_id = uuid4()
    key = f"materials/{material.id}/{version_id}.{file.extension}"
    version = MaterialVersion(
        id=version_id,
        material_id=material.id,
        version_no=number,
        status="uploaded",
        storage_key=key,
        checksum_sha256=file.checksum,
        original_filename=file.filename,
        size_bytes=len(file.data),
        created_by=user.id,
    )
    try:
        storage.put(key, file.data)
        db.add(version)
        if new_material:
            db.add(
                AuditEvent(
                    actor_id=user.id,
                    action="material.create",
                    target_type="material",
                    target_id=material.id,
                    detail={},
                )
            )
        db.add(
            AuditEvent(
                actor_id=user.id,
                action="material_version.create",
                target_type="material_version",
                target_id=version_id,
                detail={},
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(material)
    db.refresh(version)
    queue.enqueue_ingest(version_id)
    return UploadResult(
        material=LecturerMaterial.model_validate(material),
        version=VersionDetail.model_validate(version),
    )
