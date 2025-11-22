# services/product_analysis_service.py
from fastapi import Depends
from models.dtos import AnalysisScoresDTO
from repositories.food_repository import FoodRepository
from services.score_service import ScoreService

class FoodAnalysisService:
    """
    [통합된 역할]
    바코드를 주면 3대 분석 점수를 책임지고 가져옵니다.
    
    1. (조회) 이미 계산된 점수가 캐시/DB에 있다면 그거 줌
    2. (생성) 없다면? Raw 데이터 가져와서 -> 계산기 돌리고 -> 결과 반환
    """
    def __init__(
        self,
        repo: FoodRepository = Depends(FoodRepository),
        calculator: ScoreService = Depends(ScoreService) # 아까 만든 계산기
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
        
        # ---------------------------------------------------------
        # [저장] 계산된 결과를 DB에 저장
        # ---------------------------------------------------------
        self.repo.save_analysis_result(barcode, analysis_scores)

        return analysis_scores