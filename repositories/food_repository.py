# repositories/product_repository.py

from typing import List, Optional
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import text # Raw SQL 사용을 위해 text 임포트
from redis import Redis 
import os

from models.dtos import GradeResult, RawProductAPIDTO 
from database import get_db 
from dotenv import load_dotenv

# --- .env 파일 로드 ---
load_dotenv() 

# --- API 키를 .env에서 직접 읽어옴 ---
FOOD_API_KEY = os.getenv("FOOD_API_KEY") 
BASE_URL_FOOD = "http://openapi.foodsafetykorea.go.kr/api"


class FoodRepository:
    def __init__(self, db: Session = Depends(get_db)):
        # 생성자에서 주입받은 DB 세션을 self.db에 저장
        self.db = db
        # (API Key, URL 등은 config 파일에서 로드)

    def get_food_by_report_no(self, prdlst_report_no: str) -> Optional[RawProductAPIDTO]:
        """
        제품 보고 번호(prdlst_report_no)로 DB에서 제품 정보를 조회합니다.
        (TotalScoreService에서 제품 이름을 가져오기 위해 사용)
        
        [가정]
        1. DB에 'PRODUCT_INFO'라는 테이블이 존재합니다. (PRODUCT_INFO_SQL 변수명 참고)
        2. 이 테이블에는 'PRDLST_REPORT_NO' 컬럼이 있습니다.
        3. 이 테이블의 컬럼 구조는 RawProductAPIDTO와 호환됩니다.
        """
        
        # [가정] DTO에 필요한 모든 컬럼을 가져오는 쿼리
        QUERY = text("""
            SELECT * FROM PRODUCT_INFO 
            WHERE PRDLST_REPORT_NO = :report_no
        """)
        
        try:
            # self.db를 사용하여 쿼리 실행
            row = self.db.execute(QUERY, {"report_no": prdlst_report_no}).first()
            
            if row:
                # SQLAlchemy의 RowProxy를 Pydantic DTO로 변환
                return RawProductAPIDTO.model_validate(row)
            
            return None # DB에 해당 번호의 제품이 없음
            
        except Exception as e:
            # 실제 운영 코드에서는 로깅(logging)을 권장합니다.
            print(f"Error querying by report no ({prdlst_report_no}): {e}")
            return None
    # --------------------------


    def get_raw_data(self, barcode: str) -> RawProductAPIDTO:
        """
        바코드로 Raw 데이터를 가져오는 단일 메서드
        (캐시 조회->DB 조회 -> 없으면 API 호출 -> DB 저장)
        """
        # 캐시조회
        cached_data = self.cache.get(f"product:{barcode}")
        if cached_data:
            print(f"Cache Hit from REDIS for {barcode}")
            # JSON 문자열을 DTO로 변환
            return RawProductAPIDTO.model_validate_json(cached_data)
        
        #DB 조회 (main.py의 PRODUCT_INFO_SQL 사용)
        db_data = self._get_raw_from_db(barcode)
        
        if db_data:
            print(f"Cache Hit from DB for {barcode}")
            self.cache.setex(f"product:{barcode}", 3600, db_data.model_dump_json())
            return db_data # DB에 있으면 바로 반환

        # 2. DB에 없음 -> API 호출
        print(f"Cache Miss. Fetching from API for {barcode}")
        api_data_dto = self._fetch_raw_from_api(barcode)
        
        # 3. API 결과를 캐시 및 DB에 저장
        self._save_raw_to_db(api_data_dto)
        self.cache.setex(f"product:{barcode}", 3600, api_data_dto.model_dump_json())
        
        # 4. API 결과를 DB 조회 DTO 형식으로 변환하여 반환
        return RawProductAPIDTO.model_validate(api_data_dto)

    def _get_raw_from_db(self, barcode: str) -> Optional[RawProductAPIDTO]:
        """DB에서 Raw 데이터(List 2)를 조회"""
        # (main.py의 PRODUCT_INFO_SQL 쿼리 실행 로직)
        
        # [구현 예시]
        # PRODUCT_INFO_SQL = text("SELECT * FROM PRODUCT_INFO WHERE BAR_CD = :barcode")
        # try:
        #     row = self.db.execute(PRODUCT_INFO_SQL, {"barcode": barcode}).first()
        #     if row:
        #         return RawProductAPIDTO.model_validate(row)
        # except Exception as e:
        #     print(f"Error _get_raw_from_db: {e}")
        
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
        # [구현 예시]
        # INSERT_SQL = text("""
        #     INSERT INTO PRODUCT_INFO (BAR_CD, PRDLST_NM, PRDLST_REPORT_NO, ...)
        #     VALUES (:bar_cd, :prdlst_nm, :prdlst_report_no, ...)
        # """)
        # try:
        #     self.db.execute(INSERT_SQL, api_data.model_dump())
        #     self.db.commit()
        # except Exception as e:
        #     self.db.rollback()
        #     print(f"Error _save_raw_to_db: {e}")
            
        print(f"Saving {api_data.prdlst_nm} to DB...") # .name -> .prdlst_nm (DTO 가정)
        pass # (임시)
    def find_alternatives_by_rep_code(
        self, 
        rep_code: str, 
        exclude_report_no: str
    ) -> List[RawProductAPIDTO]:
        """
        대표 식품 코드(PRDLST_CD)가 일치하는 다른 제품(대안 제품) 목록을 반환합니다.
        
        - rep_code: 찾고자 하는 대표 식품 코드
        - exclude_report_no: 현재 스캔한 제품(목록에서 제외할 제품)의 보고 번호
        """
        
        # [가정] 대표 식품 코드 컬럼명이 'PRDLST_CD'라고 가정
        QUERY = text("""
            SELECT * FROM PRODUCT_INFO
            WHERE PRDLST_CD = :rep_code 
              AND PRDLST_REPORT_NO != :exclude_report_no
        """)
        
        try:
            rows = self.db.execute(QUERY, {
                "rep_code": rep_code,
                "exclude_report_no": exclude_report_no
            }).fetchall()
            
            # Pydantic DTO 리스트로 변환
            return [RawProductAPIDTO.model_validate(row) for row in rows]
        
        except Exception as e:
            print(f"Error finding alternatives ({rep_code}): {e}")
            return []