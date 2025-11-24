#routers/history_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.dtos import ScanHistoryDTO, GradeCalculationRequest, GradeResult
from services.history_service import HistoryService
from services.final_grade_calculation_service import FinalGradeCalculationService

router = APIRouter(
    prefix="/history",  
    tags=["Scan History"]
)

@router.get("/me", response_model=List[ScanHistoryDTO], summary="내 스캔 기록 목록 조회")
def get_my_scan_history(
    user_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    service: HistoryService = Depends(HistoryService)
):
    """
    현재 사용자의 최근 스캔 기록을 N개 반환
    """
    return service.get_user_scan_history(user_id, skip=skip, limit=limit)

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
    service: HistoryService = Depends(HistoryService)
):
    """
    특정 기록(scan_id)의 상세 정보를 가져옵니다.
    (내 기록이 아니면 권한 에러를 낼 수도 있음)
    """
    record = service.get_scan_history_by_id(scan_id, user_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
        
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
    db: Session = Depends(get_db),
    service: HistoryService = Depends(HistoryService)
):
    """
    특정 스캔 기록을 삭제
    """
    # 1. 존재 여부 및 권한 확인
    service.delete_scan_history(scan_id, user_id)
    
    return None # 204 No Content