# capston_app/main.py
from contextlib import asynccontextmanager
import os
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text                   # ✅ DB 헬스체크용
from pydantic import BaseModel

import capston_app.database as database
import capston_app.models as models

# ---- 환경변수 로드 (FOOD_API_KEY 등) ----
load_dotenv()
FOOD_API_KEY = os.getenv("FOOD_API_KEY")
BASE_URL = "http://openapi.foodsafetykorea.go.kr/api"

# ---- Lifespan: 앱 시작 시 테이블 생성 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(lifespan=lifespan)

# ---- DB 세션 의존성 ----
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- 기본 헬스체크 ----
@app.get("/")
def index():
    return {"message": "Hello World"}

# ---- ✅ DB 연결 확인용 ----
@app.get("/db/health")
def db_health():
    try:
        with database.engine.connect() as conn:
            one = conn.execute(text("SELECT 1")).scalar_one()
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
            version = conn.execute(text("SELECT VERSION()")).scalar()
        return {
            "ok": True,
            "select_1": one,     # 1 이면 OK
            "database": db_name, # 예: capston1
            "version": version   # MySQL 서버 버전
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# ---- 데모: 아이템 생성/조회 ----
class ItemIn(BaseModel):
    name: str
    price: float  # 입력은 float로 받고, DB에는 Numeric으로 저장

@app.post("/items")
def create_item(payload: ItemIn, db: Session = Depends(get_db)):
    obj = models.Item(name=payload.name, price=payload.price)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@app.get("/items/{item_id}")
def read_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Item, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    return obj

# ---- 바코드 조회 → DB upsert ----
@app.get("/barcode/{code}")
def fetch_and_save_product(code: str, db: Session = Depends(get_db)):
    if not FOOD_API_KEY:
        raise HTTPException(500, "FOOD_API_KEY not set in .env")

    # C005: 바코드 제품 조회 (행 범위는 필요시 조절)
    url = f"{BASE_URL}/{FOOD_API_KEY}/C005/json/1/5/BAR_CD={code}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise HTTPException(502, f"Upstream error: {r.status_code}")

    data = r.json()
    rows = data.get("C005", {}).get("row", [])
    if not rows:
        raise HTTPException(404, f"No product found for barcode {code}")

    row = rows[0]
    name    = row.get("PRDLST_NM")
    company = row.get("BSSH_NM")
    expire  = row.get("POG_DAYCNT") or row.get("PRDLST_DCNM")

    # upsert
    obj = db.query(models.Product).filter_by(barcode=code).first()
    if obj:
        obj.name, obj.company, obj.expire = name, company, expire
    else:
        obj = models.Product(barcode=code, name=name, company=company, expire=expire)
        db.add(obj)

    db.commit()
    db.refresh(obj)
    return {
        "barcode": obj.barcode,
        "name": obj.name,
        "company": obj.company,
        "expire": obj.expire,
        "saved": True,
    }

# ---- 저장된 제품 단건 조회 ----
@app.get("/products/{barcode}")
def get_saved_product(barcode: str, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter_by(barcode=barcode).first()
    if not obj:
        raise HTTPException(404, "Not saved")
    return obj
