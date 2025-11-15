# services/product_pipeline_service.py
from fastapi import Depends
from models.dtos import (
    AnalysisScoresDTO, ProductDTO, RawProductAPIDTO
)
from repositories.product_repository import ProductRepository
from services.product_normalization_service import ProductNormalizationService
#from services.packaging_analysis_service import PackagingAnalysisService
#from services.additives_analysis_service import AdditivesAnalysisService
#from services.nutrition_analysis_service import NutritionAnalysisService

class ProductPipelineService:
    """
    바코드가 주어졌을 때, 새로운 분석 점수를 생성하는 
    전체 파이프라인(API->정규화->분석->저장)을 수행하는 책임
    """
    def __init__(
        self,
        # 파이프라인 각 단계에 필요한 서비스들을 모두 주입받음
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

    def create_and_save_new_scores(self, barcode: str) -> AnalysisScoresDTO:
        """
        바코드를 사용하여 전체 분석 파이프라인을 실행하고 결과를 저장
        """
        
        # 1. [I/O] 외부 API에서 원본(Raw) 데이터 조회
        # (repo는 HTTPException을 발생시켜 오류를 전파할 수 있음)
        raw_data: RawProductAPIDTO = self.repo.fetch_raw_from_api(barcode)
        
        # 2. [가공] 원본 데이터 -> 표준 ProductDTO로 정규화
        # (이 ProductDTO가 3대 분석 서비스의 공통 입력값이 됨)
        product_dto: ProductDTO = self.normalizer.normalize(raw_data)
        
        # 3. [분석] 3대 분석 서비스가 ProductDTO를 입력받아 점수 계산
        pkg_score = self.pkg_service.analyze(product_dto)
        add_score = self.add_service.analyze(product_dto)
        nut_score = self.nut_service.analyze(product_dto)
        
        # 4. [조립] 3대 점수 + 제품 기본 정보를 AnalysisScoresDTO로 조립
        scores_to_save = AnalysisScoresDTO(
            packaging=pkg_score,
            additives=add_score,
            nutrition=nut_score,
            
            # 기본 정보는 정규화된 DTO(product_dto)에서 가져옴
            name=product_dto.name,
            image_url=product_dto.image_url,
            category_code=product_dto.category_code
        )
        
        # 5. [I/O] 완성된 3대 분석 점수를 DB/캐시에 저장
        self.repo.save_analysis_scores(barcode, scores_to_save)
        
        # 6. [반환] 저장된 최종 DTO를 반환
        return scores_to_save