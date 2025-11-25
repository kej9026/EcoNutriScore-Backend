#main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import database
from models import models
from routers import food_router, history_router, recommendation_router, user_router

# 테이블 생성
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(title="EcoNutri API", lifespan=lifespan, openapi_version="3.0.2")

# 라우터 등록
app.include_router(food_router.router)
app.include_router(history_router.router)
app.include_router(recommendation_router.router)
app.include_router(user_router.router)

@app.get("/")
def index():
    return {"message": "EcoNutri API Service"}
