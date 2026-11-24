from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from alembic import context
from app.assignments import models as assignments_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401
from app.config import get_settings
from app.courses import models as courses_models  # noqa: F401
from app.db import Base
from app.idempotency import IdempotencyKey  # noqa: F401
from app.materials import models as materials_models  # noqa: F401
from app.practice import models as practice_models  # noqa: F401
from app.progress import models as progress_models  # noqa: F401
from app.tutor import models as tutor_models  # noqa: F401

url = get_settings().database_url


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    migrate(context.config.attributes["connection"])
else:
    engine = create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 2})
    with engine.connect() as connection:
        migrate(connection)
