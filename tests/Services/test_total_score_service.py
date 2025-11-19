import pytest
from models.dtos import PackagingScore, AdditivesScore, NutritionScore, UserPrioritiesDTO
from services.final_grade_calculation_service import FinalGradeCalculationService
from repositories.score_rule_repository import ScoreRuleRepository

# -------------------------------------------------------------------
# 1. 가짜(Mock) Repository 생성
# -------------------------------------------------------------------
# TotalScoreService는 ScoreRuleRepository가 있어야 작동합니다.
# 하지만 진짜 DB에 연결할 수 없으므로, 가짜 객체를 만듭니다.

class MockScoreRuleRepository(ScoreRuleRepository):
    """
    DB나 Redis 대신, 테스트용 가짜 등급 규칙을 반환하는
    가짜 Repository 클래스
    """
    def get_grade_rules(self) -> dict:
        # 실제 DB 규칙 대신, 테스트용 규칙을 하드코딩하여 반환
        return {
            "A": 80,  # 80점 이상 A
            "B": 70,  # 70점 이상 B
            "C": 60,  # 60점 이상 C
            "E": 0    # 그 외 E
        }

# -------------------------------------------------------------------
# 2. 테스트 함수 작성 (핵심)
# -------------------------------------------------------------------
# 함수 이름은 'test_'로 시작해야 합니다.

def test_calculate_with_default_weights():
    """
    [시나리오 1] 사용자가 가중치를 입력 안 했을 때 (기본값 테스트)
    PDF의 기본 가중치(0.106, 0.633, 0.260)로 계산되는지 확인
    """
    # 1. 준비 (Arrange)
    # 가짜 Repository 인스턴스 생성
    mock_repo = MockScoreRuleRepository() 
    
    # 테스트 대상인 Service 인스턴스 생성 (가짜 repo 주입)
    service = TotalScoreService(rule_repo=mock_repo) 
    
    # 분석 모듈이 아직 없으므로, 가짜 DTO를 직접 생성
    pkg_score = PackagingScore(score=80, details=[])
    add_score = AdditivesScore(score=50, risks=[])
    nut_score = NutritionScore(score=70, highlights=[])

    # 2. 실행 (Act)
    # priorities=None (기본값)으로 함수 호출
    final_total_score, final_grade = service.total_score(
        pkg_score, add_score, nut_score, priorities=None
    )

    # 3. 검증 (Assert)
    # (80 * 0.333) + (50 * 0.333) + (70 * 0.333) 
    # = 8.48 + 31.65 + 18.2 = 66.6 -> int(66)
    # 가짜 규칙에 따르면 66점은 'D' 등급
    assert final_total_score == 66
    assert final_grade == "C"


def test_calculate_with_custom_ahp_weights():
    """
    [시나리오 2] 사용자가 가중치를 직접 입력했을 때 (AHP 테스트)
    모든 가중치를 1:1:1로 설정 (전부 1점)
    """
    # 1. 준비 (Arrange)
    mock_repo = MockScoreRuleRepository()
    service = TotalScoreService(rule_repo=mock_repo)
    
    # 모든 점수를 60점으로 통일
    pkg_score = PackagingScore(score=60, details=[])
    add_score = AdditivesScore(score=60, risks=[])
    nut_score = NutritionScore(score=60, highlights=[])
    
    # 모든 중요도를 1 (동일)로 설정
    custom_priorities = UserPrioritiesDTO(
        pkg_vs_add=1, 
        pkg_vs_nut=1, 
        add_vs_nut=1
    )

    # 2. 실행 (Act)
    # priorities에 DTO를 전달
    final_total_score, final_grade = service.total_score(
        pkg_score, add_score, nut_score, priorities=custom_priorities
    )

    # 3. 검증 (Assert)
    # 가중치가 모두 1/3 (0.333...)이 됨
    # (60 * 0.333...) + (60 * 0.333...) + (60 * 0.333...) = 60
    # 가짜 규칙에 따르면 60점은 'C' 등급
    assert final_total_score == 60
    assert final_grade == "C"