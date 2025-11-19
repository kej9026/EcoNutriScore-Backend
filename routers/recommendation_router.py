# routers/recommendation_router.py

from typing import List
from fastapi import APIRouter, Depends, Path

from services.food_recommendation_service import RecommendationService
from models.dtos import RawProductAPIDTO # 응답 DTO

# 라우터 설정
router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)

@router.get(
    "/{prdlst_report_no}/alternatives", 
    response_model=List[RawProductAPIDTO]
)
def get_alternative_recommendations(
    prdlst_report_no: str = Path(
        ..., 
        title="Product Report Number", 
        description="기준이 되는 제품의 보고 번호"
    ),
    service: RecommendationService = Depends(RecommendationService)
):
    """
    특정 제품 보고 번호(prdlst_report_no)를 기준으로,
    '대표 식품 코드'가 동일한 대안 제품 목록을 반환합니다.
    """
    return service.get_alternative_products(prdlst_report_no)