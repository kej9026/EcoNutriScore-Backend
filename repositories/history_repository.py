# /repositories/history_repository.py

from sqlalchemy.orm import Session
from typing import List
from models.models import ScanHistory  # ScanHistory 모델 경로
class HistoryRepository:
    def get_history_by_user_id(
        db: Session, user_id: int, limit: int = 20
    ) -> List[ScanHistory]:
        """
        특정 사용자의 스캔 기록을 DB에서 조회한다.
        최신순으로 정렬하여 지정된 개수(limit)만큼 반환한다.
        """
        return (
            db.query(ScanHistory)
            .filter(ScanHistory.user_id == user_id)
            .order_by(ScanHistory.scanned_at.desc())
            .limit(limit)
            .all()
        )
    def create_scan_history_with_score(
        db: Session, 
        user_id: int, 
        prdlst_report_no: str, 
        product_name: str,
        total_score: int,     
        grade: str             
    ) -> ScanHistory:
        
        db_history = ScanHistory(
            user_id=user_id,
            prdlst_report_no=prdlst_report_no,
            prdlst_nm=product_name,
            total_score=total_score,  
            grade=grade               
        )
        
        db.add(db_history)
        db.commit()
        db.refresh(db_history)
        
        return db_history