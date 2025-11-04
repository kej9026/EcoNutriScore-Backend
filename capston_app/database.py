from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. URL에서는 charset 부분을 제거합니다.
DB_URL = "mysql+pymysql://root:1234@127.0.0.1:3306/capston1"

engine = create_engine(
    DB_URL,
    # 2. 여기에 charset을 딕셔너리 형태로 전달합니다.
    connect_args={"charset": "utf8mb4"},
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()