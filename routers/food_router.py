#routers/food_router.py
from fastapi import (
    APIRouter, Depends, UploadFile, 
    File, HTTPException
)
from services.barcode_scanning_service import BarcodeScanningService
from services.food_analysis_service import FoodAnalysisService
from services.final_grade_calculation_service import FinalGradeCalculationService

from models.dtos import (
    BarcodeScanResult,       # 0단계 응답
    AnalysisScoresDTO,       # 1단계 응답
    GradeCalculationRequest, # 2단계 요청
    GradeResult              # 2단계 응답
)

router = APIRouter(
    prefix="/foods",
    tags=["Foods API"]
)

# -------------------------------------------------------------------
# 0단계: 바코드 이미지 스캔 (이미지 -> 바코드 번호)
# -------------------------------------------------------------------
@router.post("/scan-barcode-image", response_model=BarcodeScanResult)
async def scan_barcode_from_image(
    file: UploadFile = File(...),
    scanner_service: BarcodeScanningService = Depends(BarcodeScanningService)
):
    """
    [0단계] 프론트엔드에서 이미지 파일을 업로드받아 바코드를 스캔
    """
    
    # 1. HTTP 요청 유효성 검사 (MIME 타입)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    # 2. 파일 내용 읽기 (I/O)
    contents = await file.read()
    
    # 3. 실제 로직은 서비스에 위임
    # (서비스에서 404/422 HTTPException이 발생할 수 있음)
    return scanner_service.scan_image_to_barcode(contents)
    
# -------------------------------------------------------------------
# 1단계: 3가지 점수 분석 (DB/API 조회 및 분석)
# -------------------------------------------------------------------
@router.get("/analysis/{barcode}", response_model=AnalysisScoresDTO)
def get_analysis_scores(
    barcode: str,
    analysis_service: FoodAnalysisService = Depends(FoodAnalysisService)
):
    """
    [1단계] 바코드 번호(str)를 받아 3가지 분석 점수를 반환합니다.
    (DB/캐시 조회 또는 신규 생성 파이프라인 실행)
    """
    # ProductEvaluationService는 3대 분석 점수(DTO)만 반환
    return analysis_service.get_analysis_scores(barcode)

# -------------------------------------------------------------------
# 2단계: 최종 점수 계산 (실시간 가중치 적용)
# -------------------------------------------------------------------
@router.post("/calculate-grade", response_model=GradeResult)
def calculate_final_grade(
    # dtos.py에 정의된 '2단계 요청 DTO'를 사용
    request_data: GradeCalculationRequest,
    user_id: int,
    save_history: bool = True,
    grade_service: FinalGradeCalculationService = Depends(FinalGradeCalculationService)
):
    """
    [2단계] 1단계 결과(AnalysisScoresDTO)와 
    사용자 가중치(UserPrioritiesDTO)를 받아 
    최종 등급(GradeResult)을 계산
    """
    
    # 1. 요청 DTO에서 3대 점수와 가중치 추출
    analysis_scores = request_data.scores
    user_priorities = request_data.priorities
    
    # 2. TotalScoreService에 계산 위임
    final_result = grade_service.calculate_and_save(
        user_id=user_id,
        scores=analysis_scores,
        priorities=user_priorities,
        save_to_db=save_history
    )
    
    return final_result