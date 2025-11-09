#API 엔드포인트
from fastapi import APIRouter, Depends
from services.total_score_service import TotalScoreService
from models.dtos import (
    ProductDTO, GradeResult, UserPrioritiesDTO,
    PackagingScore, AdditivesScore, NutritionScore
)
#임시
from services.packaging_analysis_service import PackagingAnalysisService
from services.additives_analysis_service import AdditivesAnalysisService
from services.nutrition_analysis_service import NutritionAnalysisService

from models.dtos import AnalysisScoresDTO, GradeResult, UserPrioritiesDTO, PackagingScore, AdditivesScore, NutritionScore
from services.product_evaluation_service import ProductEvaluationService
from services.total_score_service import TotalScoreService

router = APIRouter()

# -------------------------------------------------------------------
# 1단계: 3가지 점수 분석 (DB/API 조회 및 분석)
# -------------------------------------------------------------------
@router.get("/analysis/{barcode}", response_model=AnalysisScoresDTO)
def get_analysis_scores(
    barcode: str,
    eval_service: ProductEvaluationService = Depends(ProductEvaluationService)
):
    """
    바코드로 3가지 분석 점수(포장재, 첨가물, 영양)를 조회/생성
    """
    # ProductEvaluationService는 3가지 점수만 반환
    return eval_service.get_analysis_scores(barcode)

# -------------------------------------------------------------------
# 2단계: 최종 점수 계산 (실시간 가중치 적용)
# -------------------------------------------------------------------
# 프론트가 1단계 결과와 사용자 입력을 합쳐서 보낼 Body DTO
class ScoreRequest(BaseModel):
    packaging: PackagingScore
    additives: AdditivesScore
    nutrition: NutritionScore
    priorities: Optional[UserPrioritiesDTO] = None

@router.post("/calculate-score", response_model=GradeResult)
def calculate_final_score(
    request: ScoreRequest,
    total_score_service: TotalScoreService = Depends(TotalScoreService)
):
    """
    3가지 점수와 가중치를 입력받아 최종 점수와 등급을 계산
    """
    # TotalScoreService가 최종 점수와 등급을 반환
    final_total, final_grade = total_score_service.calculate_final_score(
        request.packaging,
        request.additives,
        request.nutrition,
        request.priorities
    )
    
    return GradeResult(
        total=final_total,
        grade=final_grade,
        packaging=request.packaging,
        additives=request.additives,
        nutrition=request.nutrition
    )
    