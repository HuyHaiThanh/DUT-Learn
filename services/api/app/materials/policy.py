from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from app.deps import class_role, require_class_member
from app.materials.models import Material, MaterialVersion


def can_read_version(db: Session, user: User, version: MaterialVersion) -> bool:
    material = db.get(Material, version.material_id)
    if material is None:
        return False
    try:
        require_class_member(material.class_id, db, user)
    except HTTPException:
        return False
    return class_role(db, user, material.class_id) == "lecturer" or (
        material.active_version_id == version.id
        and version.status == "published"
        and material.visibility == "students"
    )
