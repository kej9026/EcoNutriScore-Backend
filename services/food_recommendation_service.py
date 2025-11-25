from typing import List
from fastapi import Depends, HTTPException, status
from repositories.food_repository import FoodRepository
# from services.score_service import ScoreService <-- 삭제! (이제 필요 없음)
from models.dtos import RecommendationRequestDTO, RecommendationResultDTO

class FoodRecommendationService:
    def __init__(
        self, 
        food_repo: FoodRepository = Depends(FoodRepository)
        # score_service 삭제
    ):
        self.food_repo = food_repo

    def get_alternative_products(
        self, 
        req: RecommendationRequestDTO # (DTO 이름 확인: RecommendationRequestDTO가 맞음)
    ) -> List[RecommendationResultDTO]:
        
        # 1. 원본 조회
        original_food = self.food_repo.get_food_by_report_no(req.report_no)
        if not original_food:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Original product not found.")

        # 2. 카테고리 확인
        cat_code = original_food.category_code  
        if not cat_code: return [] 

        # 3. 후보군 조회
        candidates = self.food_repo.find_alternatives(
            category_code=cat_code,
            exclude_report_no=req.report_no,
            limit=50 
        )
        if not candidates: return []

        # 4. 가중치 및 기준점수 준비
        w_pkg = req.weights.packaging_weight
        w_add = req.weights.additives_weight
        w_nut = req.weights.nutrition_weight
        standard_score = req.total_score

        # 5. 랭킹 산정
        ranked_list = []
        
        for product in candidates:
            
            # [수정] ScoreService 호출 없이, product 안에 있는 DB 점수 바로 사용!
            total_score = (
                (product.base_packaging_score * w_pkg) + 
                (product.base_additives_score * w_add) + 
                (product.base_nutrition_score * w_nut)
            )
            
            # 기준점보다 낮으면 탈락
            if total_score <= standard_score:
                continue

            grade = self._calculate_grade_letter(float(total_score))
            
            result_dto = RecommendationResultDTO(
                barcode=product.barcode,
                name=product.name,
                image_url=product.image_url,
                brand=product.brand,
                
                # [수정] DB에 있는 base 점수에 가중치를 곱해서 보여줌
                nutrition_score=product.base_nutrition_score * w_nut,
                packaging_score=product.base_packaging_score * w_pkg,
                additives_score=product.base_additives_score * w_add,
                
                total_score=float(total_score),
                grade=grade
            )
            
            ranked_list.append(result_dto)

        # 6. 정렬 (높은 순)
        ranked_list.sort(key=lambda dto: dto.total_score, reverse=True)

        # 7. Top 5 반환
        return ranked_list[:5]

    def _calculate_grade_letter(self, score: float) -> str:
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        if score >= 60: return "D"
        return "E"