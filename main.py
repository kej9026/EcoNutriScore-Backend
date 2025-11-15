# capston_app/main.py
from contextlib import asynccontextmanager
import os
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from database import get_db, engine
import models.models as models


# 서버 재시작 전 어딘가 한 번 호출 (예: 앱 시작 직후)
from database import engine
engine.dispose()

# =========================================================
# 환경 변수 (옵션: 식약처 C005 바코드 조회용)
# =========================================================
load_dotenv()
FOOD_API_KEY = os.getenv("FOOD_API_KEY")
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
# 헬스체크
# =========================================================
@app.get("/")
def index():
    return {"message": "Hello World"}

from fastapi.responses import PlainTextResponse
import json

@app.get("/db/health", response_class=PlainTextResponse)
def db_health():
    try:
        with database.engine.connect() as conn:
            one     = conn.execute(text("SELECT 1")).scalar_one()
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
            version = conn.execute(text("SELECT VERSION()")).scalar()
            vars_row = conn.execute(text(
                "SELECT @@character_set_client AS client, "
                "@@character_set_connection AS connection, "
                "@@character_set_results AS results"
            )).mappings().first()
        
        # RowMapping → dict 변환
        charset = dict(vars_row) if vars_row is not None else {}

        body = {
            "ok": True,
            "select_1": int(one),
            "database": db_name,
            "version": str(version),
            "charset": charset,
        }

        # dict → JSON 문자열 변환 후 문자열 결합
        return json.dumps(body, ensure_ascii=False)

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
# 공통 조회 SQL (제품 기본 + 영양 + 포장재 재질)
# =========================================================
PRODUCT_INFO_SQL = text("""
    SELECT
        f.barcode,
        f.name,
        f.prdlst_report_no    AS report_no,
        f.image_url           AS image_url,
        f.category_code       AS category_code,

        nf.sodium_mg          AS sodium_mg,
        nf.sugar_g            AS sugar_g,
        nf.sat_fat_g          AS sat_fat_g,
        nf.trans_fat_g        AS trans_fat_g,
        nf.additives_cnt      AS additives_cnt,

        r.material            AS packaging_material
    FROM foods f
    LEFT JOIN nutrition_facts nf ON nf.barcode = f.barcode
    LEFT JOIN recycling_info  r  ON r.barcode  = f.barcode
    WHERE f.barcode = :barcode
    LIMIT 1
""")

# (선택) ingredients 테이블이 있을 경우만 조회: ingredients(barcode, name)
INGREDIENTS_SQL = text("""
    SELECT name FROM ingredients WHERE barcode = :barcode ORDER BY 1
""")

def fetch_ingredients_safe(db: Session, barcode: str):
    try:
        rows = db.execute(INGREDIENTS_SQL, {"barcode": barcode}).fetchall()
        return [r[0] for r in rows]
    except Exception:
        # 테이블이 없거나 칼럼이 없는 경우 빈 리스트
        return []

def fetch_serving_size_safe(db: Session, barcode: str):
    # nutrition_facts.serving_size 칼럼이 있다면 읽고, 없으면 None
    try:
        row = db.execute(
            text("SELECT serving_size FROM nutrition_facts WHERE barcode=:b LIMIT 1"),
            {"b": barcode},
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None

# =========================================================
# DTO 형태로 반환 (요구된 키 그대로)
# =========================================================
@app.get("/product-dto/{barcode}")
def get_product_dto(barcode: str, db: Session = Depends(get_db)):
    base = db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).mappings().first()
    if not base:
        raise HTTPException(status_code=404, detail=f"No record for barcode {barcode}")

    ingredients = fetch_ingredients_safe(db, barcode)
    serving_size = fetch_serving_size_safe(db, barcode)

    # 표준 키 그대로 맞춰서 반환
    return {
        "barcode":             base["barcode"],
        "name":                base["name"],
        "sodium_mg":           base.get("sodium_mg"),
        "sugar_g":             base.get("sugar_g"),
        "sat_fat_g":           base.get("sat_fat_g"),
        "trans_fat_g":         base.get("trans_fat_g"),
        "packaging_material":  base.get("packaging_material"),
        "report_no":           base.get("report_no"),
        "ingredients":         ingredients,     # 테이블 없으면 []
        "image_url":           base.get("image_url"),
        "category_code":       base.get("category_code"),
        "serving_size":        serving_size,    # 칼럼 없으면 None
    }

# =========================================================
# 점수 계산 (네가 정의한 규칙 반영, 포장재는 재질명 기반)
# =========================================================
def score_range(value, bands):
    if value is None:
        return 0
    for low, high, sc in bands:
        if value >= low and value < high:
            return sc
    return 0

def score_additives(cnt):
    if cnt is None:
        return 0
    return max(0, 100 - int(cnt) * 10)

def score_trans_fat(val):
    if val is None:
        return 0
    if val == 0:
        return 25
    if val >= 0.1:
        return -50
    return 0

def score_packaging_from_material(material: str):
    if not material:
        return 0
    key = material.strip().lower()
    aliases = {
        "유리": "glass", "glass": "glass",
        "알루미늄": "aluminum", "알루미늄 캔": "aluminum",
        "aluminum": "aluminum", "aluminium": "aluminum",
        "pet": "pet", "pet 플라스틱": "pet",
        "pp": "pp", "pp 플라스틱": "pp",
        "ps": "ps", "ps 플라스틱": "ps",
        "복합재질": "composite", "복합": "composite",
        "composite": "composite", "multi": "composite",
    }
    norm = aliases.get(key)
    if norm is None:
        if "유리" in key or "glass" in key: norm = "glass"
        elif "알루" in key or "alumi" in key: norm = "aluminum"
        elif key.startswith("pet"): norm = "pet"
        elif key.startswith("pp"):  norm = "pp"
        elif key.startswith("ps"):  norm = "ps"
        elif "복합" in key or "compos" in key: norm = "composite"

    if norm == "glass":     return 95
    if norm == "aluminum":  return 95
    if norm == "pet":       return 85
    if norm == "pp":        return 60
    if norm == "ps":        return 20
    if norm == "composite": return 10
    return 0

@app.get("/product-score/{barcode}")
def product_score(barcode: str, db: Session = Depends(get_db)):
    row = db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No record for barcode {barcode}")

    sodium_score = score_range(
        row.get("sodium_mg"),
        [(0, 50, 100), (50, 120, 85), (120, 200, 70), (200, 400, 50), (400, 600, 25), (600, float("inf"), 0)],
    )
    sugar_score = score_range(
        row.get("sugar_g"),
        [(0, 1, 100), (1, 5, 85), (5, 10, 70), (10, 15, 50), (15, 22.5, 25), (22.5, float("inf"), 0)],
    )
    sat_fat_score = score_range(
        row.get("sat_fat_g"),
        [(0, 1, 40), (1, 3, 25), (3, 5, 10), (5, float("inf"), -15)],
    )
    trans_fat_score = score_trans_fat(row.get("trans_fat_g"))
    additives_score = score_additives(row.get("additives_cnt"))
    packaging_score = score_packaging_from_material(row.get("packaging_material"))

    scores = {
        "sodium":    sodium_score,
        "sugar":     sugar_score,
        "sat_fat":   sat_fat_score,
        "trans_fat": trans_fat_score,
        "additives": additives_score,
        "packaging": packaging_score,
    }
    total = sum(scores.values())
    missing = {
        "sodium_mg":          row.get("sodium_mg")          is None,
        "sugar_g":            row.get("sugar_g")            is None,
        "sat_fat_g":          row.get("sat_fat_g")          is None,
        "trans_fat_g":        row.get("trans_fat_g")        is None,
        "additives_cnt":      row.get("additives_cnt")      is None,
        "packaging_material": row.get("packaging_material") is None,
    }
    return {"barcode": row["barcode"], "name": row["name"], "scores": scores, "total": total, "missing_fields": missing}
