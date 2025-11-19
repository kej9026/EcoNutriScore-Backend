# services/recommendation_service.py

from typing import List
from fastapi import Depends, HTTPException, status
from repositories.food_repository import FoodRepository
from models.dtos import RawProductAPIDTO

class FoodRecommendationService:
    """
    제품 추천 관련 비즈니스 로직을 담당합니다.
    """
    def __init__(self, food_repo: FoodRepository = Depends(FoodRepository)):
        # FoodRepository에 의존
        self.food_repo = food_repo

    def get_alternative_products(self, prdlst_report_no: str) -> List[RawProductAPIDTO]:
        """
        주어진 제품과 동일한 '대표 식품 코드'를 가진 
        대안 제품 목록을 반환합니다.
        """
        
        # 1. 원본 제품 정보 조회
        original_food = self.food_repo.get_food_by_report_no(prdlst_report_no)

        if not original_food:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original product not found."
            )

        # 2. 원본 제품의 '대표 식품 코드' 확인
        # [중요] RawProductAPIDTO에 'prdlst_cd' 필드가 있어야 합니다.
        if not hasattr(original_food, 'prdlst_cd') or not original_food.prdlst_cd:
            # 대표 식품 코드가 없는 제품이면 빈 리스트 반환
            return [] 

        rep_code = original_food.prdlst_cd
        
        # 3. FoodRepository를 통해 대안 제품 목록 조회
        alternatives = self.food_repo.find_alternatives_by_rep_code(
            rep_code=rep_code,
            exclude_report_no=prdlst_report_no # 원본 제품은 제외
        )
        
        return alternatives