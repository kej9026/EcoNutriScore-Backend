from typing import List
from fastapi import Depends, HTTPException, status
from repositories.food_repository import FoodRepository
from models.dtos import RecommendationRequestDTO, RecommendationResultDTO

class FoodRecommendationService:
    def __init__(
        self, 
        food_repo: FoodRepository = Depends(FoodRepository)
    ):
        self.food_repo = food_repo

    def get_alternative_products(
        self, 
        req: RecommendationRequestDTO
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
            limit=100  # [팁] 중복 제거하면 개수가 줄어드니까 넉넉하게 조회 (50 -> 100)
        )
        if not candidates: return []

        # 4. 가중치 및 기준점수 준비
        w_pkg = req.weights.packaging_weight
        w_add = req.weights.additives_weight
        w_nut = req.weights.nutrition_weight
        standard_score = req.total_score

        # 5. [핵심 수정] 중복 제거를 위한 딕셔너리 (Key: 품목보고번호, Value: 데이터)
        unique_candidates = {}

        for product in candidates:
            
            # 점수 계산
            total_score = (
                (product.base_packaging_score * w_pkg) + 
                (product.base_additives_score * w_add) + 
                (product.base_nutrition_score * w_nut)
            )
            
            # 기준점보다 낮으면 탈락
            if total_score <= standard_score:
                continue

            # [중복 방지 로직]
            report_no = product.prdlst_report_no
            
            # 이미 저장된 같은 제품(report_no)이 있는지 확인
            if report_no in unique_candidates:
                # 있다면, 현재 점수가 더 높을 때만 교체 (더 좋은 옵션 선택)
                if total_score > unique_candidates[report_no]['total_score']:
                    unique_candidates[report_no] = {
                        'product': product,
                        'total_score': total_score
                    }
            else:
                # 없으면 새로 등록
                unique_candidates[report_no] = {
                    'product': product,
                    'total_score': total_score
                }

        # 6. DTO 변환 및 리스트 생성
        ranked_list = []
        
        for item in unique_candidates.values():
            product = item['product']
            final_score = float(item['total_score'])
            grade = self._calculate_grade_letter(final_score)

            result_dto = RecommendationResultDTO(
                barcode=product.barcode,
                name=product.name,
                image_url=product.image_url,
                brand=product.brand,
                
                # 상세 점수 (가중치 적용된 값)
                nutrition_score=product.base_nutrition_score * w_nut,
                packaging_score=product.base_packaging_score * w_pkg,
                additives_score=product.base_additives_score * w_add,
                
                total_score=final_score,
                grade=grade
            )
            ranked_list.append(result_dto)

        # 7. 정렬 (높은 순) 및 Top 5 반환
        ranked_list.sort(key=lambda dto: dto.total_score, reverse=True)

        return ranked_list[:5]

    def _calculate_grade_letter(self, score: float) -> str:
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        if score >= 60: return "D"
        return "E"