#등급 구간 기준을 조회
class ScoreRuleRepository:
    def __init__(self):
        #추후 DB연결
        self.cached_rules = {"A": 90, "B": 80, "C": 70, "D": 60, "E": 0}

    def get_grade_rules(self) -> dict:
        print("Repo: DB/Cache에서 등급 규칙 조회")
        # DB 조회 대신 캐시된 규칙 반환
        return self.cached_rules