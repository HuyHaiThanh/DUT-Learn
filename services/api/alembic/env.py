from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from alembic import context
from app.config import get_settings
from app.db import Base

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
