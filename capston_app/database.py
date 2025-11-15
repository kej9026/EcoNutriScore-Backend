# capston_app/database.py
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 본인 비번/호스트에 맞게 수정
DB_URL = "mysql+pymysql://root:1234@127.0.0.1:3306/capston1?charset=utf8mb4"

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
    connect_args={
        "charset": "utf8mb4",
        "use_unicode": True,
    },
)

# 모든 새 커넥션에서 문자셋 확실히 고정
@event.listens_for(engine, "connect")
def _set_names_utf8mb4(dbapi_conn, conn_rec):
    with dbapi_conn.cursor() as cur:
        cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()
