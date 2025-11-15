# services/score_retrieval_service.py
from typing import Optional
from fastapi import Depends
from models.dtos import AnalysisScoresDTO
from repositories.product_repository import ProductRepository 
# (ProductRepository가 캐시/DB 조회를 모두 처리한다고 가정)

class ScoreRetrievalService:
    """
    바코드에 해당하는 기존 분석 점수를 '조회'하는 책임을 가짐.
    (전략: 캐시 -> DB 순서로 확인)
    """
    def __init__(self, repo: ProductRepository = Depends(ProductRepository)):
        """
        데이터 접근을 위해 Repository에 의존
        """
        self.repo = repo

    def get_existing_scores(self, barcode: str) -> Optional[AnalysisScoresDTO]:
        """
        바코드를 받아 캐시 또는 DB에서 기존 분석 점수를 조회
        
        Returns:
            AnalysisScoresDTO: 점수를 찾은 경우
            None: 캐시와 DB 어디에도 점수가 없는 경우
        """
        
        # 1. 캐시에서 가져오기
        # (Repository가 캐시 로직을 추상화하여 제공한다고 가정)
        cached_scores = self.repo.get_cached_result(barcode)
        if cached_scores:
            print(f"[{barcode}] Scores found in Cache.")
            # (캐시에서 찾은 DTO를 바로 반환)
            return cached_scores

        # 2. DB에서 가져오기
        db_scores = self.repo.get_db_result(barcode)
        if db_scores:
            print(f"[{barcode}] Scores found in DB. Caching...")
            # (TODO: DB 결과를 캐시에 다시 저장하는 로직)
            # self.repo.save_result_to_cache(barcode, db_scores) 
            
            # (DB에서 찾은 DTO를 반환)
            return db_scores 

        # 3. 캐시와 DB 모두 없음
        return None