# repositories/product_repository.py

from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from redis import Redis # Redis 클라이언트 (main.py에서 주입)
import requests
import json
import os

from models.dtos import GradeResult, RawProductAPIDTO 
from database import get_db 
from dotenv import load_dotenv

# --- .env 파일 로드 ---
load_dotenv() # <-- 2. .env 파일 로드 실행

# --- API 키를 .env에서 직접 읽어옴 ---
FOOD_API_KEY = os.getenv("FOOD_API_KEY") 
BASE_URL_FOOD = "http://openapi.foodsafetykorea.go.kr/api"
# repositories/product_repository.py

class ProductRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
        # (API Key, URL 등은 config 파일에서 로드)

    def get_raw_data(self, barcode: str) -> RawProductAPIDTO:
        """
        바코드로 Raw 데이터를 가져오는 단일 메서드
        (DB 조회 -> 없으면 API 호출 -> DB 저장)
        """
        
        # 1. DB 조회 (main.py의 PRODUCT_INFO_SQL 사용)
        db_data = self._get_raw_from_db(barcode)
        
        if db_data:
            print(f"Cache Hit from DB for {barcode}")
            return db_data # DB에 있으면 바로 반환

        # 2. DB에 없음 -> API 호출
        print(f"Cache Miss. Fetching from API for {barcode}")
        api_data_dto = self._fetch_raw_from_api(barcode)
        
        # 3. API 결과를 DB에 저장 (다음 조회를 위해)
        self._save_raw_to_db(api_data_dto)
        
        # 4. API 결과를 DB 조회 DTO 형식으로 변환하여 반환
        return RawProductAPIDTO.model_validate(api_data_dto)

    def _get_raw_from_db(self, barcode: str) -> Optional[RawProductAPIDTO]:
        """DB에서 Raw 데이터(List 2)를 조회"""
        # (main.py의 PRODUCT_INFO_SQL 쿼리 실행 로직)
        # ...
        # row = self.db.execute(PRODUCT_INFO_SQL, ...).first()
        # if row:
        #    return RawProductAPIDTO.model_validate(row)
        return None # (임시)

    def _fetch_raw_from_api(self, barcode: str) -> RawProductAPIDTO:
        """API에서 Raw 데이터(List 2)를 조회"""
        # (main.py의 /barcode/{code} 로직)
        # ...
        # return RawProductAPIDTO.model_validate(rows[0])
        pass # (임시)

    def _save_raw_to_db(self, api_data: RawProductAPIDTO):
        """API 결과를 Raw 데이터 DB 테이블에 저장"""
        # (api_data를 DB 테이블 모델로 변환하여 저장)
        print(f"Saving {api_data.name} to DB...")
        pass # (임시)