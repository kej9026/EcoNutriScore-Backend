# services/product_evaluation_service.py

from fastapi import Depends
from models.dtos import (
    ProductDTO, GradeResult, UserPrioritiesDTO, 
    AnalysisScoresDTO, 
    PackagingScore, AdditivesScore, NutritionScore
)
from repositories.product_repository import ProductRepository
from services.product_normalization_service import ProductNormalizationService
from services.packaging_analysis_service import PackagingAnalysisService
from services.additives_analysis_service import AdditivesAnalysisService
from services.nutrition_analysis_service import NutritionAnalysisService

class ProductEvaluationService:
    """
    바코드 하나에 대한 3가지 분석 점수를 반환
    (캐시/DB 조회 -> 없으면 API 호출 -> 정규화 -> 분석 -> 저장)
    """
    def __init__(
        self,
        repo: ProductRepository = Depends(ProductRepository),
        normalizer: ProductNormalizationService = Depends(ProductNormalizationService),
        pkg_service: PackagingAnalysisService = Depends(PackagingAnalysisService),
        add_service: AdditivesAnalysisService = Depends(AdditivesAnalysisService),
        nut_service: NutritionAnalysisService = Depends(NutritionAnalysisService)
    ):
        self.repo = repo
        self.normalizer = normalizer
        self.pkg_service = pkg_service
        self.add_service = add_service
        self.nut_service = nut_service

    def get_analysis_scores(self, barcode: str) -> AnalysisScoresDTO:
        
        # 1. 캐시/DB에서 "3가지 중간 점수"를 가져옴
        cached_scores = self.repo.get_cached_result(barcode)
        if cached_scores:
            return cached_scores # (있으면 바로 반환)

        db_scores = self.repo.get_db_result(barcode)
        if db_scores:
            # (TODO: DB 결과를 캐시에 다시 저장)
            return db_scores # (있으면 바로 반환)

        # 3. [MISS] DB에 점수가 없음 (API 호출부터 시작)
        print("Scores not found. Starting full analysis...")
        
        # 3a. API 호출
        raw_data = self.repo.fetch_raw_from_api(barcode)
        
        # 3b. 정규화
        product_dto = self.normalizer.normalize_from_api(raw_data)
        
        # 3c. 3대 분석
        pkg_score = self.pkg_service.analyze(product_dto)
        add_score = self.add_service.analyze(product_dto)
        nut_score = self.nut_service.analyze(product_dto)
        
        # 3f. [저장] 3가지 중간 점수를 DB/캐시에 저장
        scores_to_save = AnalysisScoresDTO(
            packaging=pkg_score,
            additives=add_score,
            nutrition=nut_score,
            name=product_dto.name,
            image_url=product_dto.image_url,
            category_code=product_dto.category_code
        )
        self.repo.save_analysis_scores(barcode, scores_to_save)
        
        # 3가지 점수(scores_to_save)를 반환
        return scores_to_save