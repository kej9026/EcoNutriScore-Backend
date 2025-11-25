# /services/history_service.py

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from models.models import ScanHistory
from repositories.history_repository import HistoryRepository

# 비즈니스 로직에서 사용할 상수 (예: 반환 개수)
HISTORY_LIMIT = 20
class HistoryService:
    def __init__(self, repo: HistoryRepository = Depends(HistoryRepository)):
        self.repo = repo
    def get_user_scan_history(self, user_id: int, skip: int = 0, limit: int = 20) -> List[ScanHistory]:
        """
        사용자의 스캔 기록을 가져오는 비즈니스 로직을 처리한다.
        """
        
        # 1. 리포지토리를 통해 데이터를 조회
        return self.repo.get_user_scan_history(user_id, skip=skip, limit=limit)
    
    def get_scan_history_by_id(self, scan_id: int, user_id: int):
        return self.repo.get_scan_history_by_id(scan_id, user_id)
    
    def delete_scan_history(self, scan_id: int, user_id: int):
        """
        스캔 기록 삭제 요청 처리
        """
        # 리포지토리에게 삭제 명령 (내 기록인지 확인까지 포함됨)
        is_deleted = self.repo.delete_scan_history(scan_id, user_id)
        
        # 삭제 실패 시 (기록이 없거나 내 것이 아님)
        if not is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="기록을 찾을 수 없거나 삭제할 권한이 없습니다."
            )
        
        # 성공 시 아무것도 반환하지 않음 (Router에서 204 No Content 처리)