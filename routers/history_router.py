#routers/history_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.dtos import ScanHistoryDTO, GradeCalculationRequest, GradeResult
import services.history_service as history_service
from services.final_grade_calculation_service import FinalGradeCalculationService

router = APIRouter(
    prefix="/history",  
    tags=["Scan History"]
)
@router.post(
    "", 
    response_model=GradeResult,
    summary="스캔 수행 및 기록 저장",
    status_code=status.HTTP_201_CREATED
)
def create_scan_record(
    request_data: GradeCalculationRequest,
    user_id: int,  # (TODO: 실제로는 JWT 토큰에서 추출 권장)
    grade_service: FinalGradeCalculationService = Depends(FinalGradeCalculationService)
):
    """
    사용자가 제품을 스캔하고 가중치를 적용하여 결과를 저장
    """
    # 서비스에 위임하여 계산 및 저장 수행
    result = grade_service.calculate_and_save(
        user_id=user_id,
        scores=request_data.scores,
        priorities=request_data.priorities,
        save_to_db=True
    )
    return result

@router.get("/me", response_model=List[ScanHistoryDTO], summary="내 스캔 기록 목록 조회")
def get_my_scan_history(
    user_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    현재 사용자의 최근 스캔 기록을 N개 반환
    """
    history_records = history_service.get_user_scan_history(
        db=db, user_id=user_id, skip=skip, limit=limit
    )
    
    # ORM 모델 리스트를 Pydantic DTO 리스트로 변환
    return history_records 
    # (참고: from_attributes=True가 DTO에 설정되어 있어야 함)

# ===================================================================
# [READ] 특정 스캔 기록 상세 조회 (Detail)
# ===================================================================
@router.get(
    "/{scan_id}", 
    response_model=ScanHistoryDTO,
    summary="특정 스캔 기록 상세 조회"
)
def get_scan_history_detail(
    scan_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    특정 기록(scan_id)의 상세 정보를 가져옵니다.
    (내 기록이 아니면 권한 에러를 낼 수도 있음)
    """
    record = history_service.get_scan_history_by_id(db, scan_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    
    # 본인의 기록인지 확인 (간단한 권한 체크)
    if record.user_id != user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
        
    return record


# ===================================================================
# [DELETE] 스캔 기록 삭제
# ===================================================================
@router.delete(
    "/{scan_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="스캔 기록 삭제"
)
def delete_scan_history(
    scan_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    특정 스캔 기록을 삭제
    """
    # 1. 존재 여부 및 권한 확인
    record = history_service.get_scan_history_by_id(db, scan_id)
    if not record:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    
    if record.user_id != user_id:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")

    # 2. 삭제 수행
    history_service.delete_scan_history(db, scan_id)
    
    return None # 204 No Content