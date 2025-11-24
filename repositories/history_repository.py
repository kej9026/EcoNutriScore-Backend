# /repositories/history_repository.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from database import get_db
from models.models import ScanHistory, Food
from models.dtos import ScanHistoryDTO

class HistoryRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def get_user_scan_history(
        self, user_id: int, skip: int = 0, limit: int = 20
    ) -> List[ScanHistoryDTO]:
        """
        특정 사용자의 스캔 기록 조회 (최신순)
        """
        rows = (
            self.db.query(ScanHistory)
            .options(joinedload(ScanHistory.food)) # food 테이블 정보도 로딩해라!
            .filter(ScanHistory.user_id == user_id)
            .order_by(ScanHistory.scanned_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        # 2. 변환 (Mapping)
        result_list = []
        for row in rows:
            dto = ScanHistoryDTO(
                scan_id = row.scan_id,
                # [핵심] 다른 테이블(food)에 있는 이름을 가져옴
                product_name = row.food.name if row.food else "알 수 없음",
                image_url = row.food.image_url if row.food else None,
                
                # [핵심] DB 컬럼명(score_total) -> DTO 필드명(total_score)
                total_score = row.score_total,
                grade = row.grade,
                
                # [핵심] DB 컬럼명(scanned_at) -> DTO 필드명(created_at)
                created_at = row.scanned_at
            )
            result_list.append(dto)
            
        return result_list
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
    
    def get_scan_history_by_id(self, scan_id: int, user_id: int) -> Optional[ScanHistoryDTO]:
        # 1. DB 조회
        row = (
            self.db.query(ScanHistory)
            .options(joinedload(ScanHistory.food)) # 이름 가져오기 위해 조인
            .filter(ScanHistory.scan_id == scan_id)
            .filter(ScanHistory.user_id == user_id)
            .first()
        )
        
        if not row:
            return None

        # 2. DTO 변환 (Mapping)
        return ScanHistoryDTO(
            scan_id=row.scan_id,
            product_name=row.food.name if row.food else "알 수 없음",
            image_url=row.food.image_url if row.food else None,
            total_score=row.score_total,
            grade=row.grade,
            created_at=row.scanned_at
        )
    
    def delete_scan_history(self, scan_id: int, user_id: int) -> bool:
        """
        해당 scan_id의 기록을 삭제합니다. 
        단, user_id가 일치해야만 삭제됩니다. (본인 확인)
        반환값: 삭제 성공 여부 (True/False)
        """
        # 1. 삭제 대상 조회 (내 기록인지 확인 포함)
        record = self.db.query(ScanHistory).filter(
            ScanHistory.scan_id == scan_id,
            ScanHistory.user_id == user_id
        ).first()

        # 2. 없으면(내 거 아니거나 없는 ID면) False 반환
        if not record:
            return False

        # 3. 있으면 삭제 수행
        self.db.delete(record)
        self.db.commit()
        return True