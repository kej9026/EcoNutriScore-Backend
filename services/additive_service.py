#services/addtive_service.py
import re
from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db, SessionLocal
from models.models import Additive

class AdditiveService:
    """
    [역할] 원재료명 문자열 분석 및 유해 성분 카운팅 전담
    """
    def __init__(self):
        # 1. 생성 시점에 DB에서 금지어 목록을 메모리(Set)에 로딩
        # (매번 DB 조회하면 느리니까 캐싱)
        self.additive_set = set()
        self._load_additives()

    def _load_additives(self):
        """DB에서 첨가물 목록을 가져와 set에 저장"""
        db = SessionLocal() # 서비스 내부에서 별도 세션 사용
        try:
            additives = db.query(Additive).all()
            self.additive_set = {item.name for item in additives}
            print(f"[AdditiveService] 유해성분 {len(self.additives)}개 로드 완료")
        except Exception as e:
            print(f"[AdditiveService] 로드 실패: {e}")
        finally:
            db.close()

    def calculate_count(self, raw_text: str) -> int:
        """
        [핵심 로직] 지저분한 문자열 -> 쪼개기 -> 정규화 -> 카운트
        입력: "정제수, L-글루탐산나트륨(향미증진제), 설탕"
        출력: 1 (L-글루탐산나트륨 발견)
        """
        if not raw_text: 
            return 0
        
        count = 0
        # 1. 콤마로 분리
        ingredients = raw_text.split(",")
        
        for ing in ingredients:
            # 2. 정규화 (괄호 삭제, 공백 제거)
            # "L-글루탐산나트륨(향미증진제)" -> "L-글루탐산나트륨"
            clean_name = re.sub(r'\(.*?\)', '', ing).strip()
            
            if not clean_name: continue

            # 3. 메모리 상의 Set과 비교 (O(1) 속도)
            if clean_name in self.additive_set:
                count += 1
                # print(f"검출: {clean_name}") 

        return count