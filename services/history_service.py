# /services/history_service.py

from sqlalchemy.orm import Session
from typing import List
from models.models import ScanHistory
import repositories.history_repository as history_repository # 리포지토리 임포트

# 비즈니스 로직에서 사용할 상수 (예: 반환 개수)
HISTORY_LIMIT = 20

def get_user_scan_history(db: Session, user_id: int) -> List[ScanHistory]:
    """
    사용자의 스캔 기록을 가져오는 비즈니스 로직을 처리한다.
    """
    
    # 1. 리포지토리를 통해 데이터를 조회
    history_records = history_repository.get_history_by_user_id(
        db=db, user_id=user_id, limit=HISTORY_LIMIT
    )

    return history_records