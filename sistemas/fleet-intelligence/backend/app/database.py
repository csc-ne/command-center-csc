"""Database session and base model.

Todas as tabelas da aplicação vivem no schema `fleet_inteligence` para conviver
sem conflito com outras aplicações no mesmo banco (ex.: csc_veneza).
"""
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


DB_SCHEMA = "fleet_inteligence"


# MetaData com schema → todas as tabelas herdam automaticamente.
# Também define uma convenção de nomes para índices/constraints, útil
# quando for gerar migrations com Alembic no futuro.
metadata = MetaData(
    schema=DB_SCHEMA,
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
)


class Base(DeclarativeBase):
    metadata = metadata


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)


# Belt-and-suspenders: a cada conexão nova, garantimos que o search_path
# do Postgres inclui nosso schema. Isto cobre SQL cru e chamadas que não
# qualificam o schema explicitamente.
@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(f'SET search_path TO {DB_SCHEMA}, public')
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
