# capston_app/main.py
from contextlib import asynccontextmanager
import os
import re
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

import capston_app.database as database
import capston_app.models as models

# 서버 재시작 전 어딘가 한 번 호출 (예: 앱 시작 직후)
from capston_app.database import engine
engine.dispose()

# =========================================================
# 환경 변수 (식약처 C005 바코드 조회용 - 필요시 사용)
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

        charset = dict(vars_row) if vars_row is not None else {}

        import json
        body = {
            "ok": True,
            "select_1": int(one),
            "database": db_name,
            "version": str(version),
            "charset": charset,
        }
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

# =========================================================
# (옵션) 바코드 → 식약처 C005 조회 후 products(foods) 테이블 upsert
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
    brand   = row.get("BSSH_NM")
    report  = row.get("PRDLST_REPORT_NO")
    image   = row.get("IMG_URL")
    category = row.get("PRDLST_DCNM")  # 카테고리 코드/이름 등 필요에 맞게 수정

    obj = db.query(models.Food).filter_by(barcode=code).first()
    if obj:
        obj.name = name
        obj.brand = brand
        obj.prdlst_report_no = report
        obj.image_url = image
        obj.category_code = category
    else:
        obj = models.Food(
            barcode=code,
            name=name,
            brand=brand,
            prdlst_report_no=report,
            image_url=image,
            category_code=category,
        )
        db.add(obj)

    db.commit()
    db.refresh(obj)
    return {
        "barcode": obj.barcode,
        "name": obj.name,
        "brand": obj.brand,
        "report_no": obj.prdlst_report_no,
        "image_url": obj.image_url,
        "category_code": obj.category_code,
        "saved": True,
    }

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

        nf.serving_size       AS serving_size,   -- 예: '50ml', '100ml'
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

INGREDIENTS_SQL = text("""
    SELECT name FROM ingredients WHERE barcode = :barcode ORDER BY 1
""")

def fetch_ingredients_safe(db: Session, barcode: str):
    try:
        rows = db.execute(INGREDIENTS_SQL, {"barcode": barcode}).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []

# =========================================================
#  기준함량 문자열 → ml 숫자 변환
#   - '50ml', '100 ml', '50ML' 등 → 50.0
# =========================================================
def parse_serving_size_to_ml(serving_size: str | None) -> float | None:
    if not serving_size:
        return None
    s = serving_size.strip().lower()
    # 숫자(정수/소수)만 추출
    m = re.search(r'[\d]+(?:[.,]\d+)?', s)
    if not m:
        return None
    value = float(m.group(0).replace(",", ""))
    # 단위는 ml 기준이라고 가정 (요구사항)
    return value

# =========================================================
# 포장재 정규화: DB 문자열 → pet/pp/ps/유리/알루미늄/복합재질
# =========================================================
def normalize_material(material: str | None) -> str | None:
    if not material:
        return None

    s = material.strip().lower()

    # 우선 간단 매핑
    if "pet" in s:
        return "pet"
    if "pp" in s:
        return "pp"
    if "ps" in s:
        return "ps"
    if "유리" in s or "glass" in s:
        return "유리"
    if "알루" in s or "alumi" in s:
        return "알루미늄"

    # 나머지는 전부 복합재질로 처리
    return "복합재질"

# =========================================================
# DTO 형태로 반환 (프론트에 전달용)
# =========================================================
@app.get("/product-dto/{barcode}")
def get_product_dto(barcode: str, db: Session = Depends(get_db)):
    base = db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).mappings().first()
    if not base:
        raise HTTPException(status_code=404, detail=f"No record for barcode {barcode}")

    ingredients = fetch_ingredients_safe(db, barcode)

    serving_size_raw = base.get("serving_size")
    serving_ml = parse_serving_size_to_ml(serving_size_raw)

    # 포장재 정규화 (영문/한글 섞여 있어도 규칙대로 변환)
    raw_material = base.get("packaging_material")
    norm_material = normalize_material(raw_material)

    return {
        "barcode":             base["barcode"],
        "name":                base["name"],
        "serving_size_raw":    serving_size_raw,   # 예: '50ml'
        "serving_ml":          serving_ml,         # 예: 50.0
        "sodium_mg":           base.get("sodium_mg"),
        "sugar_g":             base.get("sugar_g"),
        "sat_fat_g":           base.get("sat_fat_g"),
        "trans_fat_g":         base.get("trans_fat_g"),
        "additives_cnt":       base.get("additives_cnt"),
        "packaging_material_raw": raw_material,
        "packaging_material":  norm_material,      # pet/pp/ps/유리/알루미늄/복합재질
        "report_no":           base.get("report_no"),
        "ingredients":         ingredients,
        "image_url":           base.get("image_url"),
        "category_code":       base.get("category_code"),
    }

# =========================================================
# 점수 계산 유틸
#  - 여기서는 이미 100ml 기준으로 환산된 값을 받는다고 가정
# =========================================================
def score_range(value, bands):
    if value is None:
        return 0
    v = float(value)
    for low, high, sc in bands:
        if v >= low and v < high:
            return sc
    return 0

def score_additives(cnt):
    if cnt is None:
        return 0
    return max(0, 100 - int(cnt) * 10)

def score_trans_fat(val):
    if val is None:
        return 0
    v = float(val)
    if v == 0:
        return 25
    if v >= 0.1:
        return -50
    return 0

def score_packaging_from_normalized(norm_material: str | None) -> int:
    if norm_material is None:
        return 0
    if norm_material == "유리":
        return 95
    if norm_material == "알루미늄":
        return 95
    if norm_material == "pet":
        return 85
    if norm_material == "pp":
        return 60
    if norm_material == "ps":
        return 20
    if norm_material == "복합재질":
        return 10
    return 0

# =========================================================
# 제품 점수 API
#  - 기준함량(serving_size) → ml 숫자 → 100ml 기준으로 환산해서 점수 계산
# =========================================================
@app.get("/product-score/{barcode}")
def product_score(barcode: str, db: Session = Depends(get_db)):
    row = db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"No record for barcode {barcode}")

    serving_size_raw = row.get("serving_size")
    serving_ml = parse_serving_size_to_ml(serving_size_raw)

    # 100ml 기준 환산 계수 n
    if serving_ml and serving_ml > 0:
        n = 100.0 / serving_ml
    else:
        n = 1.0  # 기준함량 정보 없으면 스케일링 안함

    # 100ml 기준 값으로 스케일링
    sodium_100 = row.get("sodium_mg")
    sugar_100 = row.get("sugar_g")
    sat_fat_100 = row.get("sat_fat_g")
    trans_fat_100 = row.get("trans_fat_g")

    if sodium_100 is not None:
        sodium_100 = float(sodium_100) * n
    if sugar_100 is not None:
        sugar_100 = float(sugar_100) * n
    if sat_fat_100 is not None:
        sat_fat_100 = float(sat_fat_100) * n
    if trans_fat_100 is not None:
        trans_fat_100 = float(trans_fat_100) * n

    # 포장재 정규화
    norm_material = normalize_material(row.get("packaging_material"))

    # 점수 계산 (예시 band는 이전과 동일하게 유지)
    sodium_score = score_range(
        sodium_100,
        [(0, 50, 100), (50, 120, 85), (120, 200, 70),
         (200, 400, 50), (400, 600, 25), (600, float("inf"), 0)],
    )
    sugar_score = score_range(
        sugar_100,
        [(0, 1, 100), (1, 5, 85), (5, 10, 70),
         (10, 15, 50), (15, 22.5, 25), (22.5, float("inf"), 0)],
    )
    sat_fat_score = score_range(
        sat_fat_100,
        [(0, 1, 40), (1, 3, 25), (3, 5, 10), (5, float("inf"), -15)],
    )
    trans_fat_score = score_trans_fat(trans_fat_100)
    additives_score = score_additives(row.get("additives_cnt"))
    packaging_score = score_packaging_from_normalized(norm_material)

    scores = {
        "sodium":    sodium_score,
        "sugar":     sugar_score,
        "sat_fat":   sat_fat_score,
        "trans_fat": trans_fat_score,
        "additives": additives_score,
        "packaging": packaging_score,
    }
    total = sum(scores.values())

    return {
        "barcode": row["barcode"],
        "name": row["name"],
        "serving_size_raw": serving_size_raw,
        "serving_ml": serving_ml,
        "scale_to_100ml": n,
        "normalized_values_per_100ml": {
            "sodium_mg": sodium_100,
            "sugar_g": sugar_100,
            "sat_fat_g": sat_fat_100,
            "trans_fat_g": trans_fat_100,
        },
        "packaging_material_raw": row.get("packaging_material"),
        "packaging_material": norm_material,
        "scores": scores,
        "total": total,
    }
