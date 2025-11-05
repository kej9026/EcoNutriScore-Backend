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

# ------------------------------
# 환경 변수
# ------------------------------
load_dotenv()
FOOD_API_KEY  = os.getenv("FOOD_API_KEY")      # 식품의약품안전처(foodsafetykorea) 키
HACCP_API_KEY = os.getenv("HACCP_API_KEY")     # data.go.kr HACCP 이미지/표기정보 키 (추가)
BASE_URL_FOOD  = "http://openapi.foodsafetykorea.go.kr/api"
BASE_URL_HACCP = "https://apis.data.go.kr/B553748/CertImgListServiceV3"

# ------------------------------
# 앱 수명주기: 테이블 자동 생성
# ------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(lifespan=lifespan)

# ------------------------------
# DB 세션 DI
# ------------------------------
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------
# 헬스체크
# ------------------------------
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

# ------------------------------
# 데모 Item
# ------------------------------
class ItemIn(BaseModel):
    name: str
    price: float   # 금액 정밀도까지 필요하면 Numeric로 모델 변경 가능

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

# ------------------------------
# 바코드 → 식약처 C005 조회 후 저장
# ------------------------------
@app.get("/barcode/{code}")
def fetch_and_save_product(code: str, db: Session = Depends(get_db)):
    if not FOOD_API_KEY:
        raise HTTPException(500, "FOOD_API_KEY not set in .env")

    # C005: 식품 바코드 제품 조회
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

@app.get("/products/{barcode}")
def get_saved_product(barcode: str, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter_by(barcode=barcode).first()
    if not obj:
        raise HTTPException(404, "Not saved")
    return obj

# ------------------------------
# HACCP 제품 이미지/포장지표기 정보 (data.go.kr)
#   문서: B553748/CertImgListServiceV3
#   - /getCertImgListServiceV3
#   - 파라미터는 기관 가이드에 따라 prdlstNm(제품명) 또는 barCd(바코드) 사용
# ------------------------------
def _call_haccp(params: dict):
    """HACCP API 호출 헬퍼 (JSON)"""
    if not HACCP_API_KEY:
        raise HTTPException(500, "HACCP_API_KEY not set in .env")

    # 공통 파라미터
    base_params = {
        "serviceKey": HACCP_API_KEY,  # 인코딩키 그대로 넣어도 requests가 처리
        "returnType": "json",
        "pageNo": params.pop("pageNo", 1),
        "numOfRows": params.pop("numOfRows", 10),
    }
    base_params.update(params)

    url = f"{BASE_URL_HACCP}/getCertImgListServiceV3"
    resp = requests.get(url, params=base_params, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(502, f"HACCP upstream error: {resp.status_code}")
    return resp.json()

def _extract_haccp_rows(payload: dict):
    """
    기관 응답 스키마가 가끔 바뀌므로 키가 없을 때도 안전하게 파싱.
    실제 키 이름은 문서의 필드명을 확인해 맞춰야 한다.
    """
    # 대표적으로 'body' → 'items' → 'item' 구조를 많이 사용함
    body = (payload.get("body") or
            payload.get("response", {}).get("body") or
            payload.get("getCertImgListServiceV3", {}).get("body") or {})
    items = body.get("items") or body.get("item") or []
    if isinstance(items, dict):
        items = items.get("item", []) or [items]
    return items

@app.get("/haccp/search")
def haccp_search_by_name(
    name: str = Query(..., description="제품명(부분검색)"),
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
):
    """
    제품명으로 HACCP 이미지/표기정보 조회 → 일부 필드만 추려서 반환
    """
    payload = _call_haccp({"prdlstNm": name, "pageNo": page, "numOfRows": size})
    items = _extract_haccp_rows(payload)

    results = []
    for it in items:
        # 문서의 실제 필드명에 맞춰 get 키를 바꿔 주면 됨
        results.append({
            "barcode": it.get("barCd") or it.get("BAR_CD"),
            "product_name": it.get("prdlstNm") or it.get("PRDLST_NM"),
            "manufacturer": it.get("manufacture") or it.get("BSSH_NM") or it.get("manufacturer"),
            "img_url": it.get("imgUrl") or it.get("IMG_URL"),
            "pack_img_url": it.get("packImgUrl") or it.get("PACK_IMG_URL"),
            "meta_img_url": it.get("metaImgUrl") or it.get("META_IMG_URL"),
        })
    return {"count": len(results), "items": results}

@app.get("/haccp/by-barcode/{code}")
def haccp_by_barcode(code: str, db: Session = Depends(get_db)):
    """
    바코드로 HACCP 이미지/표기정보 조회 → DB에 upsert 저장 후 반환
    """
    payload = _call_haccp({"barCd": code, "pageNo": 1, "numOfRows": 1})
    items = _extract_haccp_rows(payload)
    if not items:
        raise HTTPException(404, f"No HACCP info for barcode {code}")

    it = items[0]
    record = dict(
        barcode      = it.get("barCd") or it.get("BAR_CD") or code,
        product_name = it.get("prdlstNm") or it.get("PRDLST_NM"),
        manufacturer = it.get("manufacture") or it.get("BSSH_NM") or it.get("manufacturer"),
        img_url      = it.get("imgUrl") or it.get("IMG_URL"),
        pack_img_url = it.get("packImgUrl") or it.get("PACK_IMG_URL"),
        meta_img_url = it.get("metaImgUrl") or it.get("META_IMG_URL"),
    )

    # upsert 저장
    row = (
        db.query(models.ProductHaccp)
        .filter_by(barcode=record["barcode"], product_name=record["product_name"])
        .first()
    )
    if row:
        row.manufacturer = record["manufacturer"]
        row.img_url      = record["img_url"]
        row.pack_img_url = record["pack_img_url"]
        row.meta_img_url = record["meta_img_url"]
    else:
        row = models.ProductHaccp(**record)
        db.add(row)

    db.commit()
    db.refresh(row)
    return row
