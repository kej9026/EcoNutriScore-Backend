import numpy as np
from typing import Tuple, Dict
from fastapi import Depends
from sqlalchemy.orm import Session

from models.dtos import (
    AnalysisScoresDTO, 
    UserPrioritiesDTO, 
    GradeResult,
    UserWeightsDTO
)
from repositories.history_repository import HistoryRepository

# 기본 가중치 (사용자 입력 없을 시)
DEFAULT_WEIGHTS = {"pkg": 0.333, "add": 0.333, "nut": 0.333}

class FinalGradeCalculationService:
    def __init__(self, scan_repo: HistoryRepository = Depends(HistoryRepository)):
        self.scan_repo = scan_repo

    def _calculate_ahp(self, p: UserPrioritiesDTO) -> Dict[str, float]:
        """
        [백엔드 핵심 로직] AHP(계층화 분석법) 가중치 계산
        입력: 사용자 비교 값 (1~9)
        출력: 계산된 가중치 (합이 1.0이 되는 float 값들)
        """
        # 1. 쌍대 비교 행렬 생성 (3x3)
        # 순서: [0]포장재, [1]첨가물, [2]영양
        matrix = np.ones((3, 3)) # 대각선은 1로 초기화

        def get_val_pair(value: int):
            if value == 0: 
                return 1.0, 1.0
            
            val = float(abs(value)) + 1.0

            if value > 0:
                # 오른쪽이 더 중요 (분모로 들어감)
                return 1.0 / val, val
            else:
                # 왼쪽이 더 중요 (분자로 들어감)
                return val, 1.0 / val
        
        # 포장 vs 첨가
        v1, v2 = get_val_pair(p.pkg_vs_add)
        matrix[0, 1] = v1
        matrix[1, 0] = v2

        # 포장 vs 영양
        v1, v2 = get_val_pair(p.pkg_vs_nut)
        matrix[0, 2] = v1
        matrix[2, 0] = v2

        # 첨가 vs 영양
        v1, v2 = get_val_pair(p.add_vs_nut)
        matrix[1, 2] = v1
        matrix[2, 1] = v2

        # 2. 가중치 계산 (열 합계에 의한 정규화법)
        col_sum = matrix.sum(axis=0)       # 열 합계
        normalized = matrix / col_sum      # 정규화
        weights = normalized.mean(axis=1)  # 행 평균 = 최종 가중치

        return {
            "pkg": float(weights[0]),
            "add": float(weights[1]),
            "nut": float(weights[2])
        }

    def calculate_and_save(
        self, 
        user_id: int, 
        scores: AnalysisScoresDTO, 
        priorities: UserPrioritiesDTO, 
        save_to_db: bool = True
    ) -> GradeResult:
        
        # 1. [AHP 계산] 백엔드에서 가중치 산출
        weights_map = self._calculate_ahp(priorities)
        
        w_pkg = weights_map["pkg"]
        w_add = weights_map["add"]
        w_nut = weights_map["nut"]

        # 2. [총점 계산] (3대 점수 * 가중치)
        # (3대 점수는 100점 만점 기준이라고 가정)
        s_pkg = scores.packaging.score
        s_add = scores.additives.score
        s_nut = scores.nutrition.score

        # 가중 평균 (Weights 합은 1.0이므로 나누기 불필요)
        total_val = (s_pkg * w_pkg) + (s_add * w_add) + (s_nut * w_nut)
        final_total_score = float(total_val)

        # 3. [등급 산정]
        final_grade = self._calculate_grade_letter(final_total_score)

        # 4. [DB 저장]
        scan_id = None
        if save_to_db:
            saved_record = self.scan_repo.create_scan_history(
                user_id=user_id,
                barcode=scores.barcode,

                total_score=final_total_score,
                grade=final_grade,
                
                nutrition_score=s_nut,
                packaging_score=s_pkg,
                additives_score=s_add,
                
                w_nutrition=w_nut,
                w_packaging=w_pkg,
                w_additives=w_add
            )
            scan_id = saved_record.scan_id

        # 5. [결과 반환]
        calculated_weights = UserWeightsDTO(
            packaging_weight=w_pkg,
            additives_weight=w_add,
            nutrition_weight=w_nut
        )

        return GradeResult(
            scan_id=scan_id,
            user_id=user_id,
            name=scores.name,
            grade=final_grade,
            total_score=final_total_score,
            
            # 여기서 계산된 가중치를 돌려줍니다
            weights=calculated_weights,
            
            nutrition_score=s_nut,
            packaging_score=s_pkg,
            additives_score=s_add
        )

    def _calculate_grade_letter(self, score: float) -> str:
        # (점수 기준은 필요에 따라 조정)
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        if score >= 60: return "D"
        return "E"