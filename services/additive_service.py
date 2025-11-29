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
        """DB에서 첨가물 목록을 가져와 깨끗하게 청소해서 set에 저장"""
        db = SessionLocal()
        try:
            additives = db.query(Additive).all()
            
            # 여기가 핵심 수정 부분입니다.
            cleaned_names = set()
            for item in additives:
                if not item.name: continue
                
                # 1단계: 괄호 '(' 기준으로 쪼개서 앞부분만 가져옴
                # 예: "구연산¶(Citric Acid)" -> "구연산¶"
                temp_name = item.name.split('(')[0]
                
                # 2단계: 특수문자/기호(¶) 제거 (한글,영어,숫자,하이픈(-),점(.), 공백만 남김)
                # "구연산¶" -> "구연산"
                # "L-글루탐산나트륨" -> "L-글루탐산나트륨" (유지됨)
                clean_name = re.sub(r'[^가-힣a-zA-Z0-9\s\-\.]', '', temp_name).strip()
                
                if clean_name:
                    cleaned_names.add(clean_name)

            self.additive_set = cleaned_names
            print(f"[AdditiveService] 유해성분 {len(self.additive_set)}개 로드 및 청소 완료")
            
            # (디버깅용) 청소 잘 됐나 몇 개만 출력해보기
            # print(f"청소 예시: {list(self.additive_set)[:5]}")

        except Exception as e:
            print(f"[AdditiveService] 로드 실패: {e}")
        finally:
            db.close()

    def calculate_count(self, raw_text: str) -> tuple[int, str]:
        """
        [변경점]
        입력: "정제수, L-글루탐산나트륨(향미증진제), 설탕, 아질산나트륨"
        출력: (2, "L-글루탐산나트륨, 아질산나트륨")  <-- (개수, 콤마로 이은 목록)
        """
        if not raw_text: 
            return 0, ""
        
        detected_list = [] # 발견된 첨가물을 담을 리스트
        
        # 1. 콤마로 분리
        ingredients = raw_text.split(",")
        
        for ing in ingredients:
            # 2. 입력된 텍스트 정규화 (괄호 내용 삭제, 공백 제거)
            clean_name = re.sub(r'\(.*?\)', '', ing).strip()
            
            if not clean_name: continue

            # 3. DB 목록과 비교 (일치하면 리스트에 추가)
            if clean_name in self.additive_set:
                # 중복 방지 (같은 게 두 번 적혀 있을 수도 있으니까)
                if clean_name not in detected_list:
                    detected_list.append(clean_name)

        # 4. 결과 가공
        count = len(detected_list)
        # 리스트를 "항목1, 항목2" 문자열로 변환
        result_str = ", ".join(detected_list) 

        return count, result_str