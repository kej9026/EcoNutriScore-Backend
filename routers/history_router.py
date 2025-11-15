from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.models import ScanHistory 
from models.dtos import ScanHistoryDTO 

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
    history_records = (
        db.query(ScanHistory)
        .filter(ScanHistory.user_id == user_id)
        .order_by(ScanHistory.scanned_at.desc())
        .limit(20)
        .all()
    )
    
    # ORM 모델 리스트를 Pydantic DTO 리스트로 변환
    return history_records 
    # (참고: from_attributes=True가 DTO에 설정되어 있어야 함)