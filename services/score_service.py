#services/score_service.py
import re
from typing import Optional, List, Tuple
from models.dtos import (
    RawProductAPIDTO, 
    AnalysisScoresDTO, 
    NutritionDetail, 
    PackagingDetail, 
    AdditivesDetail
)

class ScoreService:
    """
    [점수 계산기]
    Raw 데이터를 받아서 -> 정규화(ml 변환, 재질 매핑) -> 점수 산출을 담당
    """

    def calculate_all(self, raw: RawProductAPIDTO) -> AnalysisScoresDTO:
        # 1. 단위 변환 (Serving Size -> ml)
        serving_ml = self._parse_serving_size(raw.serving_size)
        
        # 100ml 기준 환산 계수 (n)
        # serving_ml이 0이거나 없으면 그냥 1.0으로 처리 (에러 방지)
        scale = (100.0 / serving_ml) if (serving_ml and serving_ml > 0) else 1.0

        # 2. 각 분야별 점수 계산
        nut_detail = self._calc_nutrition_score(raw, scale, serving_ml)
        pkg_detail = self._calc_packaging_score(raw.packaging_material)
        add_detail = self._calc_additives_score(raw)

        # 3. 결과 DTO 조립
        return AnalysisScoresDTO(
            barcode=raw.barcode,
            name=raw.name,
            image_url=raw.image_url,
            report_no=raw.report_no,
            # 계산된 상세 점수들
            nutrition=nut_detail,
            packaging=pkg_detail,
            additives=add_detail
        )

    # =====================================================
    # [로직 1] 영양 점수 계산
    # =====================================================
    def _calc_nutrition_score(self, raw: RawProductAPIDTO, scale: float, serving_ml: float) -> NutritionDetail:
        # 안전하게 float 변환 (없으면 0)
        sodium = self._safe_float(raw.sodium_mg)
        sugar = self._safe_float(raw.sugar_g)
        sat_fat = self._safe_float(raw.sat_fat_g)
        trans_fat = self._safe_float(raw.trans_fat_g)

        # 100ml 기준으로 값 변환
        sod_100 = sodium * scale
        sug_100 = sugar * scale
        fat_100 = sat_fat * scale
        trans_100 = trans_fat * scale

        # 구간별 점수 계산
        score_sod = self._score_range(sod_100, [(0, 50, 100), (50, 120, 85), (120, 200, 70), (200, 400, 50), (400, 600, 25), (600, float('inf'), 0)])
        score_sug = self._score_range(sug_100, [(0, 1, 100), (1, 5, 85), (5, 10, 70), (10, 15, 50), (15, 22.5, 25), (22.5, float('inf'), 0)])
        score_fat = self._score_range(fat_100, [(0, 1, 40), (1, 3, 25), (3, 5, 10), (5, float('inf'), -15)])
        
        # 트랜스지방 로직
        score_trans = 25 if trans_100 == 0 else (-50 if trans_100 >= 0.1 else 0)

        # 총점 합산
        scores = [score_sod, score_sug, score_fat, score_trans]
        total_nut_score = sum(scores) / len(scores)
        
        return NutritionDetail(
            score=total_nut_score,
            sodium_mg=sodium,
            sugar_g=sugar,
            sat_fat_g=sat_fat,
            trans_fat_g=trans_fat,
            serving_ml=serving_ml
        )

    def _score_range(self, val: float, bands: List[Tuple[float, float, int]]) -> int:
        """범위에 따른 점수 반환"""
        for low, high, score in bands:
            if low <= val < high:
                return score
        return 0

    # =====================================================
    # [로직 2] 포장재 점수 계산
    # =====================================================
    def _calc_packaging_score(self, material_raw: Optional[str]) -> PackagingDetail:
        norm_mat = self._normalize_material(material_raw)
        
        # 점수표
        score_map = {
            "유리": 95, "캔류": 95, "종이": 90, "PET": 85,
            "PP": 60, "PE": 50, "PS": 20, "복합재질": 10
        }
        # 매핑 안 되면 0점
        score = float(score_map.get(norm_mat, 0))

        return PackagingDetail(
            score=score,
            material=norm_mat,
            raw_material=material_raw
        )

    def _normalize_material(self, material: Optional[str]) -> str:
        """
        재질명 정규화
        - 한글/영어 동의어 처리 (폴리에틸렌 -> PE)
        - 복합 재질 감지 (PET, PP -> 복합재질)
        """
        if not material: 
            return "기타"
        
        s = material.lower().replace(" ", "") # 공백 제거하고 소문자로

        # 1. '복합', 'other'가 명시적으로 있으면 바로 리턴
        if "복합" in s or "other" in s:
            return "복합재질"

        # 2. 매핑 테이블 (검색 키워드 -> 표준 이름)
        # 긴 단어부터 매칭되도록 순서는 크게 상관없으나, 중복 방지를 위해 집합 사용
        keyword_map = {
            # [PET]
            "폴리에틸렌테레프탈레이트": "PET",
            "pet": "PET",
            "페트": "PET",
            
            # [PE] - 폴리에틸렌이 PET에 포함되지 않도록 주의 필요하나, 
            # 보통 데이터가 '폴리에틸렌' 단독으로 오거나 'PE'로 옴
            "hdpe": "PE",
            "ldpe": "PE",
            "lldpe": "PE",
            "폴리에틸렌": "PE", 
            "pe": "PE",
            
            # [PP]
            "폴리프로필렌": "PP",
            "pp": "PP",
            
            # [PS]
            "폴리스티렌": "PS",
            "ps": "PS",
            
            # [알루미늄/캔]
            "알루미늄": "캔류",
            "aluminum": "캔류",
            "alu": "캔류",
            "캔": "캔류",
            "캔류": "캔류",
            
            # [유리]
            "유리": "유리",
            "glass": "유리",
            
            # [종이]
            "종이": "종이",
            "펄프": "종이",
            "paper": "종이"
        }

        found_materials = set() # 중복 없는 집합 (Set)

        # 3. 매핑 테이블을 돌면서 포함된 재질 찾기
        for keyword, standard_name in keyword_map.items():
            if keyword in s:
                # [예외 처리] 
                # "폴리에틸렌테레프탈레이트"(PET) 안에 "폴리에틸렌"(PE) 글자가 들어있음.
                # 이를 방지하기 위해 PET가 이미 발견되었다면 PE는 무시하는 로직 등 필요
                
                # 간단한 해결: "폴리에틸렌"을 찾았는데, 만약 "테레프탈레이트"도 문자열에 있다면?
                # -> 이건 PET이므로 PE 추가를 안 함.
                if standard_name == "PE" and "테레프탈레이트" in s:
                    continue
                
                found_materials.add(standard_name)

        # 4. 결과 판정
        if len(found_materials) == 0:
            return "기타"
        
        elif len(found_materials) == 1:
            # 하나만 발견되면 그 재질 리턴 (예: "PE")
            return list(found_materials)[0]
        
        else:
            # 두 개 이상 발견되면 복합재질 (예: "뚜껑:PP, 본체:PET" -> {PP, PET} -> 복합재질)
            # print(f"복합재질 감지됨: {material} -> {found_materials}")
            return "복합재질"

    # =====================================================
    # [로직 3] 첨가물 점수 계산
    # =====================================================
    def _calc_additives_score(self, raw: RawProductAPIDTO) -> AdditivesDetail:
        count = int(raw.additives_cnt) if raw.additives_cnt else 0
        # 개당 10점 감점 (100점 만점)
        score = float(max(0, 100 - count * 10))
        
        return AdditivesDetail(
            score=score,
            count=count,
            raw_materials = raw.raw_materials,
            additive_list_str = raw.additive_list_str
        )

    # =====================================================
    # [유틸] 파싱 및 변환
    # =====================================================
    def _parse_serving_size(self, size_str: Optional[str]) -> float:
        """'50ml' -> 50.0 변환"""
        if not size_str: return 0.0
        try:
            # 숫자만 추출
            m = re.search(r'[\d]+(?:[.,]\d+)?', str(size_str))
            if m:
                return float(m.group(0).replace(',', ''))
            return 0.0
        except:
            return 0.0

    def _safe_float(self, val):
        if not val: return 0.0
        try: return float(str(val).replace(",", ""))
        except: return 0.0