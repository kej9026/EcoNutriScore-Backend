from typing import List
from fastapi import APIRouter, Depends, Path, Query
from services.food_recommendation_service import FoodRecommendationService
from models.dtos import RecommendationRequestDTO, RecommendationResultDTO

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)

@router.post(
    "/alternatives", 
    response_model=List[RecommendationResultDTO],
    summary="사용자 맞춤 대안 제품 추천"
)
def get_alternative_recommendations(
    request: RecommendationRequestDTO, 
    service: FoodRecommendationService = Depends(FoodRecommendationService)
):
    return service.get_alternative_products(request)