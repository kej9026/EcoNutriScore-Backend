# services/product_evaluation_service.py
from fastapi import Depends
from models.dtos import AnalysisScoresDTO

# 수행 서비스들 import
from services.score_retrieval_service import ScoreRetrievalService
from services.product_pipeline_service import ProductPipelineService
# TotalScoreService 의존성 제거!

class ProductEvaluationService:
    """
    바코드를 받아 3대 분석 점수(AnalysisScoresDTO)를 반환하는 책임을 짐.
    (가중치 계산은 이 서비스의 책임이 아님)
    1. (Retrieval) 3대 분석 점수 조회 시도
    2. (Pipeline)  없으면, 신규 생성
    """
    def __init__(
        self,
        retriever: ScoreRetrievalService = Depends(ScoreRetrievalService),
        pipeline: ProductPipelineService = Depends(ProductPipelineService)
    ):
        self.retriever = retriever
        self.pipeline = pipeline

    def get_analysis_scores(self, barcode: str) -> AnalysisScoresDTO:
        """
        바코드를 받아 3대 분석 점수를 조회하거나 생성하여 반환
        """
        
        # --- [흐름 1: 3대 분석 점수 확보(AnalysisScoresDTO)] ---
        
        analysis_scores: AnalysisScoresDTO | None
        analysis_scores = self.retriever.get_existing_scores(barcode)
        
        if not analysis_scores:
            print(f"[{barcode}] Scores not found. Starting full analysis pipeline...")
            analysis_scores = self.pipeline.create_and_save_new_scores(barcode)
        else:
            print(f"[{barcode}] Scores found in cache/DB.")
            
        
        # 획득한 3대 분석 점수를 그대로 반환
        return analysis_scores