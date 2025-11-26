# repositories/food_repository.py
import os
import json
import requests
from typing import Optional, List
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import text
from redis import Redis
from dotenv import load_dotenv
from models.models import Food, NutritionFact, RecyclingInfo, Additive
from models.dtos import RawProductAPIDTO 
from database import get_db 
from dotenv import load_dotenv
from services.additive_service import AdditiveService
from services.score_service import ScoreService

load_dotenv() 

class FoodRepository:
    def __init__(self, db: Session = Depends(get_db),
                 additive_service: AdditiveService = Depends(AdditiveService),
                 score_service: ScoreService = Depends(ScoreService)):
        self.db = db
        self.food_api_key = os.getenv("FOOD_API_KEY")       # 식약처
        self.data_go_kr_key = os.getenv("DATA_GO_KR_API_KEY") # 공공데이터포털
        self.base_url_food = "http://openapi.foodsafetykorea.go.kr/api"
        self.base_url_nutri = "http://api.data.go.kr/openapi/tn_pubr_public_nutri_process_info_api"
        self.base_url_img = "https://apis.data.go.kr/B553748/CertImgListServiceV3/getCertImgListServiceV3"
        self.additive_service = additive_service
        self.score_service = score_service
        # [Redis 연결] 
        # 로컬/도커 환경에 맞게 호스트 설정 (기본: localhost)
        # decode_responses=True 필수 (bytes -> str 자동 변환)
        self.redis = Redis(host='4.236.184.102', port=6379, db=0, decode_responses=True)

    def get_raw_data(self, barcode: str) -> RawProductAPIDTO:
        """
        [흐름] 
        1. Redis 캐시 확인 (제일 빠름)
        2. DB 확인 (테이블 3개 조인)
        3. API 확인 (외부 통신)
        """
        
        # ---------------------------------------------------------
        # 1. Redis 캐시 조회
        # ---------------------------------------------------------
        try:
            cached_data = self.redis.get(f"product:{barcode}")
            if cached_data:
                print(f"[Repo] Redis Cache Hit: {barcode}")
                # JSON 문자열 -> Pydantic DTO 변환
                return RawProductAPIDTO.model_validate_json(cached_data)
        except Exception as e:
            print(f"Redis Error (Ignored): {e}")

        # ---------------------------------------------------------
        # 2. DB 조회 (JOIN 사용)
        # ---------------------------------------------------------
        # Food + Nutrition + Recycling 정보를 한 번에 가져옴
        food_obj = self.db.query(Food).options(
            joinedload(Food.nutrition),
            joinedload(Food.recycling)
        ).filter(Food.barcode == barcode).first()

        if food_obj:
            print(f"[Repo] DB Hit (Joined): {barcode}")
            dto = self._entity_to_dto(food_obj)
            
            # [캐싱] DB에서 찾은거 Redis에 저장 (1시간)
            self._cache_data(barcode, dto)
            return dto

        # ---------------------------------------------------------
        # 3. API 호출
        # ---------------------------------------------------------
        print(f"[Repo] API Fetching sequence started for: {barcode}")
        api_dto = self._fetch_full_data_sequence(barcode)

        # 4. 저장 & 캐싱
        self._save_to_db_split(api_dto)
        self._cache_data(barcode, api_dto)
        
        return api_dto

    def _cache_data(self, barcode: str, dto: RawProductAPIDTO):
        """Redis에 데이터 저장 (TTL 3600초)"""
        try:
            self.redis.setex(
                f"product:{barcode}", 
                3600, 
                dto.model_dump_json() # DTO -> JSON 문자열 변환
            )
        except Exception as e:
            print(f"Redis Save Error: {e}")

    def _fetch_full_data_sequence(self, barcode: str) -> Optional[RawProductAPIDTO]:
        if not self.food_api_key or not self.data_go_kr_key:
            print("API Keys missing!")
            return None

        # --- Step 1: C005 (기본 정보 & 보고번호 따기) ---
        c005_url = f"{self.base_url_food}/{self.food_api_key}/C005/json/1/5/BAR_CD={barcode}"
        try:
            r = requests.get(c005_url, timeout=5)
            row_c005 = r.json().get("C005", {}).get("row", [])
            
            if not row_c005:
                # 데이터 없으면 404 던짐
                raise HTTPException(status_code=404, detail="Product not found in External API (C005)")
            
            base_info = row_c005[0]
            report_no = base_info.get("PRDLST_REPORT_NO")
            product_name = base_info.get("PRDLST_NM")
            brand_name = base_info.get("BSSH_NM")
            
            print(f"Step 1 Done. Report No: {report_no}")

        except HTTPException as he:
            raise he # [중요] 404 에러는 잡지 말고 밖으로 던져야 함!
        except Exception as e:
            print(f"C005 Error: {e}")
            raise HTTPException(status_code=404, detail="Product not found (C005 Error)")

        # 보고번호 없으면 200 리턴할지, 404 할지 결정 (여기선 일단 기존 로직 유지하거나 404)
        if not report_no:
             # 보고번호가 없으면 뒤에 API들 조회가 불가능하므로 여기서 404
             raise HTTPException(status_code=404, detail="Product report number not found")

        # --- Step 2: I1250 (포장재질) ---
        pack_material = "기타"
        try:
            i1250_url = f"{self.base_url_food}/{self.food_api_key}/I1250/json/1/5/PRDLST_REPORT_NO={report_no}"
            r = requests.get(i1250_url, timeout=3)
            
            if r.status_code >= 400:
                raise HTTPException(status_code=404, detail="External API Error (I1250)")
                
            rows = r.json().get("I1250", {}).get("row", [])
            if rows:
                pack_material = rows[0].get("FRMLC_MTRQLT", "기타")
            else:
                # 데이터 없으면 404 던짐
                raise HTTPException(status_code=404, detail="Product not found in External API (I1250)")
        
        except HTTPException as he:
            raise he # [중요] 잡은 404를 다시 던져서 함수를 종료시킴
        except Exception as e: 
            print(f"I1250 Error: {e}")
            # 알 수 없는 에러도 일단 넘길지, 멈출지 결정. (여기선 로그 찍고 진행한다고 가정하면 pass, 멈추려면 raise)
            # 멈추고 싶으면 아래 주석 해제
            # raise HTTPException(status_code=404, detail="Error in I1250")

        # --- Step 3: C002 (원재료명) ---
        raw_materials = None
        calculated_additives_cnt = 0
        try:
            c002_url = f"{self.base_url_food}/{self.food_api_key}/C002/json/1/5/PRDLST_REPORT_NO={report_no}"
            r = requests.get(c002_url, timeout=3)
            
            if r.status_code >= 400:
                raise HTTPException(status_code=404, detail="External API Error (C002)")

            rows = r.json().get("C002", {}).get("row", [])
            if rows:
                raw_materials = rows[0].get("RAWMTRL_NM")
                if raw_materials:
                    calculated_additives_cnt = self.additive_service.calculate_count(raw_materials)
            else:
                raise HTTPException(status_code=404, detail="Product not found in External API (C002)")
        
        except HTTPException as he:
            raise he # [중요] 404 재발생
        except Exception as e: 
            print(f"C002 Error: {e}")

        # --- Step 4: 공공데이터포털 영양성분 API ---
        nut_dict = {}
        try:
            params = {
                "serviceKey": self.data_go_kr_key,
                "itemMnftrRptNo": report_no,
                "type": "json",
                "numOfRows": "1"
            }
            r = requests.get(self.base_url_nutri, params=params, timeout=5)
            
            if r.status_code >= 400:
                raise HTTPException(status_code=404, detail="External API Error (Nutri)")

            data = r.json()
            items = []
            if "response" in data and "body" in data["response"]:
                items = data["response"]["body"].get("items", [])
            elif "body" in data:
                 items = data["body"].get("items", [])
            
            if items:
                item = items[0]
                nut_dict = {
                    "serving_size": item.get("nutConSrtrQua"),
                    "sodium": item.get("nat"),
                    "sugar": item.get("sugar"),
                    "sat_fat": item.get("fasat"),
                    "trans_fat": item.get("fatrn"),
                    "category_code": item.get("foodLv4Cd"),
                    "category_name" : item.get("foodLv4Nm")
                }
            else:
                raise HTTPException(status_code=404, detail="Product not found in External API (Nutri)")
        
        except HTTPException as he:
            raise he # [중요] 404 재발생
        except Exception as e: 
            print(f"Nutri API Error: {e}")

        # --- Step 5: 이미지 (이미지는 없어도 404 안 띄우고 진행) ---
        image_url = None
        try:
            params = { "serviceKey": self.data_go_kr_key, "prdlstReportNo": report_no, "returnType": "json" }
            r = requests.get(self.base_url_img, params=params, timeout=5)
            data = r.json()
            items = data.get("body", {}).get("items", [])
            if items:
                new_img = items[0].get("item", {}).get("imgurl1")
                if new_img: image_url = new_img
        except Exception as e: print(f"Img API Error: {e}")

        # --- 최종 DTO 조립 ---
        return RawProductAPIDTO(
            barcode=barcode,
            name=product_name,
            brand=brand_name,
            report_no=report_no,
            category_code=nut_dict.get("category_code"), 
            category_name=nut_dict.get("category_name"),
            image_url=image_url,
            serving_size=nut_dict.get("serving_size", "0"),
            sodium_mg=nut_dict.get("sodium", "0"),
            sugar_g=nut_dict.get("sugar", "0"),
            sat_fat_g=nut_dict.get("sat_fat", "0"),
            trans_fat_g=nut_dict.get("trans_fat", "0"),
            packaging_material=pack_material,
            additives_cnt=calculated_additives_cnt
        )   

    def _save_to_db_split(self, dto: RawProductAPIDTO):
        """[핵심] DTO 하나를 쪼개서 여러 테이블에 저장"""
        try:
            scores = self.score_service.calculate_all(dto)
            # 1. Food 테이블
            new_food = Food(
                barcode=dto.barcode,
                name=dto.name,                # PRDLST_NM -> name
                brand=dto.brand,              # BSSH_NM -> brand
                prdlst_report_no=dto.report_no, # PRDLST_REPORT_NO -> report_no
                category_code=dto.category_code,
                category_name=dto.category_name,
                image_url=dto.image_url,       # IMG_URL -> image_url
                base_nutrition_score=scores.nutrition.score,
                base_packaging_score=scores.packaging.score,
                base_additives_score=scores.additives.score
            )
            self.db.add(new_food)
            
            # 2. NutritionFact 테이블
            new_nut = NutritionFact(
                barcode=dto.barcode,
                serving_size=dto.serving_size,
                sodium_mg=self._safe_float(dto.sodium_mg),
                sugar_g=self._safe_float(dto.sugar_g),
                sat_fat_g=self._safe_float(dto.sat_fat_g),
                trans_fat_g=self._safe_float(dto.trans_fat_g),
                additives_cnt=dto.additives_cnt
            )
            self.db.add(new_nut)
            
            # 3. RecyclingInfo 테이블
            new_recy = RecyclingInfo(
                barcode=dto.barcode,
                material=dto.packaging_material,
                recycling_rate=0 
            )
            self.db.add(new_recy)

            self.db.commit()
            print(f"[Repo] Saved split data for {dto.name}")

        except Exception as e:
            self.db.rollback()
            # 이미 있으면 패스하거나 로그만 찍음 (중복 저장 방지)
            print(f"DB Save Split Error: {e}")

    def _entity_to_dto(self, entity: Food) -> RawProductAPIDTO:
        """JOIN된 객체 -> DTO 변환"""
        nut = entity.nutrition
        recy = entity.recycling

        return RawProductAPIDTO(
            barcode=entity.barcode,
            name=entity.name,
            brand=entity.brand,
            report_no=entity.prdlst_report_no,
            category_code=entity.category_code,
            category_name=entity.category_name,
            image_url=entity.image_url,
            base_nutrition_score=entity.base_nutrition_score,
            base_packaging_score=entity.base_packaging_score,
            base_additives_score=entity.base_additives_score,
            # 연관 객체에서 데이터 꺼내기
            serving_size=nut.serving_size if nut else None,
            sodium_mg=str(nut.sodium_mg) if nut else "0",
            sugar_g=str(nut.sugar_g) if nut else "0",
            sat_fat_g=str(nut.sat_fat_g) if nut else "0",
            trans_fat_g=str(nut.trans_fat_g) if nut else "0",
            additives_cnt=nut.additives_cnt if nut else 0,
            
            packaging_material=recy.material if recy else None
        )

    def _safe_float(self, val):
        if not val: return 0
        try: return float(str(val).replace(",", ""))
        except: return 0

    def _count_additives(self, text: str) -> int:
        """원재료명 텍스트를 쪼개서 DB 목록(Set)에 있는지 확인"""
        if not text: return 0
        count = 0
        # 쉼표로 쪼개고 앞뒤 공백 제거
        ingredients = [x.strip() for x in text.split(",")]
        
        for ing in ingredients:
            # DB 목록에 있는지 확인 (O(1) 속도)
            if ing in self.additive_set:
                count += 1
        return count
    def get_food_by_report_no(self, report_no: str) -> Optional[RawProductAPIDTO]:
        """보고번호로 제품 찾기 (추천 서비스용)"""
        print(f"🔍 [Repo] 찾는 보고번호: '{report_no}' (길이: {len(report_no)})")
        
        food_obj = self.db.query(Food).filter(Food.prdlst_report_no == report_no).first()
        
        if food_obj:
            print(f"✅ [Repo] 찾았다! ID: {food_obj.food_id}, 이름: {food_obj.name}")
            return self._entity_to_dto(food_obj)
        
        print("❌ [Repo] DB에 없음!")
        return None
    
    def find_alternatives(self, category_code: str, exclude_report_no: str, limit: int = 5) -> List[RawProductAPIDTO]:
        """
        같은 카테고리(category_code)의 다른 제품들을 조회
        - exclude_report_no: 현재 보고 있는 제품은 제외
        """
        foods = self.db.query(Food).options(
            joinedload(Food.nutrition),
            joinedload(Food.recycling)
        ).filter(
            Food.category_code == category_code,
            Food.prdlst_report_no != exclude_report_no
        ).limit(limit).all()

        return [self._entity_to_dto(f) for f in foods]