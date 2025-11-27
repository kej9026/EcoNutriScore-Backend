# services/product_analysis_service.py
from fastapi import Depends
from models.dtos import AnalysisScoresDTO
from repositories.food_repository import FoodRepository
from services.score_service import ScoreService

class FoodAnalysisService:
    """
    [통합된 역할]
    바코드를 받아 3대 분석 점수를 가져오고 계산 위임
    
    1. (조회) 이미 계산된 점수가 캐시/DB에 있다면 그거 줌
    2. (생성) 없다면? Raw 데이터 가져와서 -> 계산기 돌리고 -> 결과 반환
    """
    def __init__(
        self,
        repo: FoodRepository = Depends(FoodRepository),
        calculator: ScoreService = Depends(ScoreService)
    ):
        self.repo = repo
        self.calculator = calculator

    def get_analysis_scores(self, barcode: str) -> AnalysisScoresDTO:
        # ---------------------------------------------------------
        # [확보] 원본(Raw) 데이터 가져오기
        # ---------------------------------------------------------
        raw_data = self.repo.get_raw_data(barcode)
        
        # ---------------------------------------------------------
        # [계산] ScoreService에게 계산 위임
        # ---------------------------------------------------------
        analysis_scores = self.calculator.calculate_all(raw_data)

        return analysis_scores