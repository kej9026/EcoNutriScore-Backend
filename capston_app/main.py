# capston_app/main.py
from contextlib import asynccontextmanager
import os
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

import capston_app.database as database
import capston_app.models as models

# =========================================================
# 환경 변수
# =========================================================
load_dotenv()
FOOD_API_KEY = os.getenv("FOOD_API_KEY")  # (옵션) 식약처 C005 바코드 조회용
BASE_URL_FOOD = "http://openapi.foodsafetykorea.go.kr/api"

# =========================================================
# 앱 수명주기: 테이블 자동 생성
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(lifespan=lifespan)

# =========================================================
# DB 세션 DI
# =========================================================
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================================================
# 헬스체크
# =========================================================
@app.get("/")
def index():
    return {"message": "Hello World"}

@app.get("/db/health")
def db_health():
    try:
        with database.engine.connect() as conn:
            one     = conn.execute(text("SELECT 1")).scalar_one()
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
            version = conn.execute(text("SELECT VERSION()")).scalar()
        return {"ok": True, "select_1": one, "database": db_name, "version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

# =========================================================
# 데모 Item
# =========================================================
class ItemIn(BaseModel):
    name: str
    price: float

@app.post("/items")
def create_item(payload: ItemIn, db: Session = Depends(get_db)):
    obj = models.Item(name=payload.name, price=payload.price)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.get("/items/{item_id}")
def read_item(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Item, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Item not found")
    return obj

# =========================================================
# (옵션) 바코드 → 식약처 C005 조회 후 products 테이블 upsert
# =========================================================
@app.get("/barcode/{code}")
def fetch_and_save_product(code: str, db: Session = Depends(get_db)):
    if not FOOD_API_KEY:
        raise HTTPException(500, "FOOD_API_KEY not set in .env")

    url = f"{BASE_URL_FOOD}/{FOOD_API_KEY}/C005/json/1/5/BAR_CD={code}"
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

    obj = db.query(models.Product).filter_by(barcode=code).first()
    if obj:
        obj.name, obj.company, obj.expire = name, company, expire
    else:
        obj = models.Product(barcode=code, name=name, company=company, expire=expire)
        db.add(obj)

    db.commit(); db.refresh(obj)
    return {
        "barcode": obj.barcode,
        "name": obj.name,
        "company": obj.company,
        "expire": obj.expire,
        "saved": True,
    }

@app.get("/products/{barcode}")
def get_saved_product(barcode: str, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter_by(barcode=barcode).first()
    if not obj:
        raise HTTPException(404, "Not saved")
    return obj

# =========================================================
# 핵심: 바코드로 DB 조회 → 나트륨/당류/지방/첨가물/재활용율 가져오기
# ---------------------------------------------------------
# 예상 스키마(예시)
#   - products(barcode PK, name ...)
#   - nutrition_facts(barcode FK, sodium_mg, sugar_g, sat_fat_g, trans_fat_g, additives_cnt)
#   - recycling_info(barcode FK, recycling_rate)
# 실제 테이블/칼럼명이 다르면 아래 SQL의 컬럼/테이블만 맞춰서 수정하세요.
# =========================================================
PRODUCT_INFO_SQL = text("""
    SELECT
        f.barcode,
        f.name,

        -- 영양 성분
        nf.sodium_mg       AS sodium_mg,
        nf.sugar_g         AS sugar_g,
        nf.sat_fat_g       AS sat_fat_g,
        nf.trans_fat_g     AS trans_fat_g,
        nf.additives_cnt   AS additives_cnt,

        -- 재활용율
        r.recycling_rate   AS recycling_rate

    FROM foods f
    LEFT JOIN nutrition_facts nf ON nf.barcode = f.barcode
    LEFT JOIN recycling_info  r  ON r.barcode  = f.barcode
    WHERE f.barcode = :barcode
    LIMIT 1
""")

@app.get("/product-info/{barcode}")
def get_product_info(barcode: str, db: Session = Depends(get_db)):
    """
    바코드로 제품 ‘영양 + 첨가물 + 재활용’ 정보를 한 번에 조회
    """
    row = db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No record for barcode {barcode}")

    # 내부 변수처럼 쓰고 싶으면 여기서 꺼내 쓰면 됩니다.
    sodium_mg     = row.get("sodium_mg")
    sugar_g       = row.get("sugar_g")
    sat_fat_g     = row.get("sat_fat_g")
    trans_fat_g   = row.get("trans_fat_g")
    additives_cnt = row.get("additives_cnt")
    recycling_rt  = row.get("recycling_rate")

    # JSON 응답
    return {
        "barcode": row["barcode"],
        "name": row["name"],
        "nutrients": {
            "sodium_mg":   sodium_mg,
            "sugar_g":     sugar_g,
            "sat_fat_g":   sat_fat_g,
            "trans_fat_g": trans_fat_g,
        },
        "additives_cnt":  additives_cnt,
        "recycling_rate": recycling_rt,
    }

# =========================================================
# (선택) 점수 계산의 뼈대만 미리 달아두기 — 규칙 확정되면 로직 채워넣기
# =========================================================
@app.get("/product-score/{barcode}")
def score_product(barcode: str, db: Session = Depends(get_db)):
    row = db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No record for barcode {barcode}")

    # 예: 간단한 예시 규칙 (엑셀 기준 확정되면 교체)
    def score_nutrient(value, thresholds):
        # thresholds = [(cut, score), ...] 큰 값일수록 감점이라면 내림차순
        for cut, sc in thresholds:
            if value is None:  # 값없음 처리
                return 0
            if value >= cut:
                return sc
        return 0

    sodium_score = score_nutrient(row.get("sodium_mg"), [(600, -40), (400, -25), (200, -10)])
    sugar_score  = score_nutrient(row.get("sugar_g"),   [(50,  -50), (25,  -25), (10,  -10)])
    fat_score    = score_nutrient((row.get("sat_fat_g") or 0), [(5, -25), (3, -10)])
    trans_score  = score_nutrient((row.get("trans_fat_g") or 0), [(0.1, -50)])
    add_score    = score_nutrient((row.get("additives_cnt") or 0), [(10, -10), (5, -5), (1, -1)])
    # 재활용 가점(예시): 95=+10, 85=+8, 60=+6, 20=+2, 복합재질(<=10)=+1
    rec = row.get("recycling_rate") or 0
    if rec >= 95: rec_score = +10
    elif rec >= 85: rec_score = +8
    elif rec >= 60: rec_score = +6
    elif rec >= 20: rec_score = +2
    elif rec > 0: rec_score = +1
    else: rec_score = 0

    total = 100 + sodium_score + sugar_score + fat_score + trans_score + add_score + rec_score

    return {
        "barcode": row["barcode"],
        "name": row["name"],
        "scores": {
            "base": 100,
            "sodium": sodium_score,
            "sugar": sugar_score,
            "sat_fat": fat_score,
            "trans_fat": trans_score,
            "additives": add_score,
            "recycling": rec_score,
        },
        "total": total
    }
