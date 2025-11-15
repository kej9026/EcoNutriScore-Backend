# +++ 바코드 스캔 라이브러리 임포트 +++
import io
from pyzbar.pyzbar import decode
from PIL import Image

# +++ FastAPI 파일 업로드 및 pydantic 기본 모델 임포트 +++
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel  # BaseModel 임포트 확인
from typing import Optional     # Optional 임포트 확인


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

from services.barcode_scanning_service import BarcodeScanningService
from models.dtos import AnalysisScoresDTO, GradeResult, UserPrioritiesDTO, PackagingScore, AdditivesScore, NutritionScore
from services.product_evaluation_service import ProductEvaluationService
from services.total_score_service import TotalScoreService

router = APIRouter()

# -------------------------------------------------------------------
# 0단계: 바코드 이미지 스캔 (이미지 -> 바코드 번호)
# -------------------------------------------------------------------
@router.post("/scan-barcode-image", response_model=BarcodeScanResult)
async def scan_barcode_from_image(
    file: UploadFile = File(...),
    # +++ BarcodeScanningService를 의존성 주입(DI) 받음 +++
    scanner_service: BarcodeScanningService = Depends(BarcodeScanningService)
):
    """
    [0단계] 프론트엔드에서 이미지 파일을 업로드받아 스캐너 서비스로 넘깁니다.
    라우터는 파일 I/O와 HTTP 요청 검사만 담당합니다.
    """
    
    # 1. 라우터의 역할: HTTP 요청 유효성 검사 (MIME 타입)
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    # 2. 라우터의 역할: 파일 내용 읽기 (I/O)
    contents = await file.read()
    
    # 3. 서비스의 역할: 실제 로직 수행 (서비스에 위임)
    #    서비스에서 발생한 HTTPException은 FastAPI가 자동으로 처리해줌
    return scanner_service.scan_image_to_barcode(contents)
    
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
    