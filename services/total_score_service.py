#실제 점수 통합 및 $\text{AHP}$ 로직 구현
from typing import Optional, Tuple
from fastapi import Depends
from repositories.score_rule_repository import ScoreRuleRepository
from models.dtos import PackagingScore, AdditivesScore, NutritionScore, UserPrioritiesDTO
import numpy as np

#기본 가중치
DEFAULT_WEIGHTS = {
    "pkg_weight": 0.333,  # 포장재
    "add_weight": 0.333,  # 첨가물
    "nut_weight": 0.333   # 영양
}

class TotalScoreService:
    #생성자에서 Repository를 주입받음
    def __init__(self, rule_repo: ScoreRuleRepository = Depends(ScoreRuleRepository)):
        self.rule_repo = rule_repo

    def _calculate_ahp_weights(self, priorities: UserPrioritiesDTO) -> dict:
        #쌍대 비교 행렬 생성 (포장재, 첨가물, 영양 순서)
        #A[i, j] = i가 j보다 얼마나 중요한가 (A[j, i] = 1 / A[i, j])
        matrix = np.zeros((3, 3))
        
        # 주 대각선은 1
        matrix[0, 0] = 1.0  # 포장재 vs 포장재
        matrix[1, 1] = 1.0  # 첨가물 vs 첨가물
        matrix[2, 2] = 1.0  # 영양 vs 영양
        
        # 사용자가 입력한 값 (1~9 척도)
        val_pkg_add = priorities.pkg_vs_add
        val_pkg_nut = priorities.pkg_vs_nut
        val_add_nut = priorities.add_vs_nut
        
        matrix[0, 1] = val_pkg_add      # 포장재 > 첨가물
        matrix[1, 0] = 1.0 / val_pkg_add  # 첨가물 < 포장재
        
        matrix[0, 2] = val_pkg_nut      # 포장재 > 영양
        matrix[2, 0] = 1.0 / val_pkg_nut  # 영양 < 포장재
        
        matrix[1, 2] = val_add_nut      # 첨가물 > 영양
        matrix[2, 1] = 1.0 / val_add_nut  # 영양 < 첨가물
        
        #고유 벡터 계산 (가중치)
        col_sum = matrix.sum(axis=0)
        normalized_matrix = matrix / col_sum
        weights = normalized_matrix.mean(axis=1)
        
        return {
            "pkg_weight": weights[0], # 포장재 가중치
            "add_weight": weights[1], # 첨가물 가중치
            "nut_weight": weights[2]  # 영양 가중치
        }
    
    #핵심 비즈니스 로직 (점수 통합)
    def total_score(self, 
        pkg_score: PackagingScore, 
        add_score: AdditivesScore, 
        nut_score: NutritionScore,
        priorities: Optional[UserPrioritiesDTO]=None
        ) -> Tuple[int,str]:

        weights = {}
        #AHP 계산
        if priorities:
            # 시나리오 1: 사용자가 우선순위를 입력함 (맞춤형)
            weights = self._calculate_ahp_weights(priorities)
        else:
            # 시나리오 2: 사용자가 입력을 안 함 (기본값)
            weights = DEFAULT_WEIGHTS
        total_score = (
            (pkg_score.score * weights["pkg_weight"]) +
            (add_score.score * weights["add_weight"]) +
            (nut_score.score * weights["nut_weight"])
        )

        final_total_score = int(total_score)
        #DB에서 등급 규칙 조회
        rules = self.rule_repo.get_grade_rules() 
        
        for grade, min_score in rules.items():
            if final_total_score >= min_score:
                return final_total_score, grade
        return final_total_score, "E"