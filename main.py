#main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import database
from models import models
from routers import food_router, history_router, recommendation_router, user_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 테이블 생성
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(title="EcoNutri API", lifespan=lifespan, openapi_version="3.0.2")

origins = [
    "http://localhost:3000",             # 프론트엔드 로컬 개발 주소
    "http://127.0.0.1:3000",             
    "https://dongjae-isaac.github.io",   
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # 허용할 사이트 목록
    allow_credentials=True,     # 로그인 쿠키 등 허용
    allow_methods=["*"],        # GET, POST, PUT, DELETE 다 허용
    allow_headers=["*"],        # 모든 헤더 허용
)

# 라우터 등록
app.include_router(food_router.router)
app.include_router(history_router.router)
app.include_router(recommendation_router.router)
app.include_router(user_router.router)

@app.get("/")
def index():
    return {"message": "EcoNutri API Service"}
