# /repositories/history_repository.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.models import ScanHistory, Food

class HistoryRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def get_history_by_user_id(
        self, user_id: int, limit: int = 20
    ) -> List[ScanHistory]:
        """
        특정 사용자의 스캔 기록 조회 (최신순)
        """
        return (
            self.db.query(ScanHistory)
            .filter(ScanHistory.user_id == user_id)
            .order_by(ScanHistory.scanned_at.desc())
            .limit(limit)
            .all()
        )

    def create_scan_history(
        self, 
        user_id: int, 
        barcode: str,          # 바코드를 받아서 food_id를 찾아야 함
        # product_name은 저장 안 함 (Food 테이블에 있으니까)
        
        total_score: float, 
        grade: str,
        
        nutrition_score: float,
        packaging_score: float,
        additives_score: float,
        
        w_nutrition: float,
        w_packaging: float,
        w_additives: float
    ) -> ScanHistory:
        
        # 1. barcode로 food_id 찾기
        food = self.db.query(Food).filter(Food.barcode == barcode).first()
        if not food:
            # 방금 1단계 분석을 마쳤으니 없을 리가 없지만, 안전장치
            raise HTTPException(404, "Food not found for history saving")

        # 2. 저장 (food_id 사용)
        db_history = ScanHistory(
            user_id=user_id,
            food_id=food.food_id, #바코드 대신 ID 저장
            
            score_total=total_score,
            grade=grade,
            
            nutrition_score=nutrition_score,
            packaging_score=packaging_score,
            additives_score=additives_score,
            
            nutrition_weight=w_nutrition,
            packaging_weight=w_packaging,
            additives_weight=w_additives
        )
        
        self.db.add(db_history)
        self.db.commit()
        self.db.refresh(db_history)
        
        return db_history