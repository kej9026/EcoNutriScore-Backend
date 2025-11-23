# services/food_recommendation_service.py
from typing import List
from fastapi import Depends, HTTPException, status
from repositories.food_repository import FoodRepository
from models.dtos import RawProductAPIDTO

class FoodRecommendationService:
    """
    [제품 추천 서비스]
    현재 제품과 같은 카테고리의 다른 제품들을 찾아줍니다.
    """
    def __init__(self, food_repo: FoodRepository = Depends(FoodRepository)):
        self.food_repo = food_repo

    def get_alternative_products(self, prdlst_report_no: str) -> List[RawProductAPIDTO]:
        """
        주어진 제품(보고번호)과 동일한 카테고리 코드를 가진 
        대안 제품 목록을 반환합니다.
        """
        
        # 1. 원본 제품 정보 조회
        original_food = self.food_repo.get_food_by_report_no(prdlst_report_no)

        if not original_food:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Original product not found (Report No: {prdlst_report_no})"
            )

        # 2. 카테고리 코드 확인
        cat_code = original_food.category
        
        if not cat_code:
            # 카테고리 정보가 없으면 추천 불가 -> 빈 리스트 반환
            print(f"[Recommend] No category code for {original_food.name}")
            return [] 

        # 3. 같은 카테고리의 다른 제품 조회
        alternatives = self.food_repo.find_alternatives(
            category_code=cat_code,
            exclude_report_no=prdlst_report_no, # 원본은 뺌
            limit=5 # 최대 5개만 추천
        )
        
        return alternatives