from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.dtos import ScanHistoryDTO 
import services.history_service as history_service

router = APIRouter(
    prefix="/history",  
    tags=["Scan History"]
)

@router.get("/me", response_model=List[ScanHistoryDTO])
def get_my_scan_history(
    user_id: int, # (TODO: user_id를 JWT 토큰 등에서 가져와야 함)
    db: Session = Depends(get_db)
):
    """
    현재 사용자의 최근 스캔 기록을 N개 반환
    """
    history_records = history_service.get_user_scan_history(
        db=db, user_id=user_id
    )
    
    # ORM 모델 리스트를 Pydantic DTO 리스트로 변환
    return history_records 
    # (참고: from_attributes=True가 DTO에 설정되어 있어야 함)