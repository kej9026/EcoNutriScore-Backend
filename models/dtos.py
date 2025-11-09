# models/dtos.py

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# -------------------------------------------------------------------
# 0. 공통 타입 정의(수정 예정)
# -------------------------------------------------------------------
Grade = Literal['A', 'B', 'C', 'D', 'E']

# -------------------------------------------------------------------
# 1. 분석 엔진 입력 DTO (Input)
# -------------------------------------------------------------------
# (ProductDTO를 구성하는 하위 DTO들) 전부 수정 예정

class PackagingDTO(BaseModel):
    """제품 DTO의 일부: 포장재 정보"""
    part: str        # 예: '용기', '뚜껑'
    material: str    # 예: 'PET', 'PP'
    label_info: Optional[str] = None

class AdditiveDTO(BaseModel):
    """제품 DTO의 일부: 첨가물 정보"""
    name: str        # 예: '아스파탐'
    function: Optional[str] = None  # 예: '감미료'

class NutritionDTO(BaseModel):
    """제품 DTO의 일부: 영양소 정보"""
    nutrient: str    # 예: '나트륨', '당류'
    amount: float    # 수치
    unit: str        # 'mg', 'g' 등 단위

class ProductDTO(BaseModel):
    """분석 엔진의 핵심 입력 DTO (정규화가 완료된 표준 데이터)"""
    product_code: str
    name: str
    category: Optional[str] = None
    packaging: List[PackagingDTO]
    additives: List[AdditiveDTO]
    nutrition: List[NutritionDTO]

# -------------------------------------------------------------------
# 2. TotalScoreService 입력 DTO (Intermediate)
# -------------------------------------------------------------------
# (각 분석 서비스가 TotalScoreService로 전달하는 중간 점수) 자유롭게 수정하시면 됩니다

class PackagingScore(BaseModel):
    score: int
    details: List[dict] # 세부 평가 내역

class AdditivesScore(BaseModel):
    score: int
    risks: List[dict]   # 위험도 평가 내역

class NutritionScore(BaseModel):
    score: int
    highlights: List[dict] # 영양 상태 하이라이트

# (AHP 가중치 계산을 위해 사용자가 입력하는 상대적 중요도)
class UserPrioritiesDTO(BaseModel):
    pkg_vs_add: int = Field(..., ge=1, le=9, description="포장재 vs 첨가물 중요도 (1~9)")
    pkg_vs_nut: int = Field(..., ge=1, le=9, description="포장재 vs 영양 중요도 (1~9)")
    add_vs_nut: int = Field(..., ge=1, le=9, description="첨가물 vs 영양 중요도 (1~9)")

# -------------------------------------------------------------------
# Repository가 DB에서 가져온 Raw 데이터를 담을 DTO
# -------------------------------------------------------------------
class RawProductAPIDTO(BaseModel):
    """
    ProductRepository가 API에서 조회한 날(Raw) 데이터를 담는 DTO
    ProductNormalizationService의 입력으로 사용
    """
    "바코드, 품목제조보고번호 등 필드명 API와 유사하게"

    class Config:
        # DB의 Row 객체를 Pydantic 모델로 자동 변환 허용
        from_attributes = True
        extra = 'ignore' # API가 모르는 필드를 보내도 무시


class AnalysisScoresDTO(BaseModel):
    """
    DB/캐시에 저장되는 중간 분석 결과 (3가지 점수)
    ProductEvaluationService의 반환값이자 /analysis의 응답
    """
    packaging: PackagingScore
    additives: AdditivesScore
    nutrition: NutritionScore
    name: str 
    image_url: Optional[str] = None
    category_code: Optional[str] = None
    
    class Config:
        from_attributes = True # DB 모델에서 바로 변환

class ProductDTO(BaseModel):
    """
    분석 엔진의 핵심 입력 DTO (정규화가 완료된 표준 데이터)
    ProductNormalizationService의 최종 출력물
    """
    # 기본 정보
    product_code: str
    name: str
    report_no: Optional[str] = None
    image_url: Optional[str] = None
    category_code: Optional[str] = None
    serving_size: Optional[str] = None
    sodium_mg: Optional[float] = None
    sugar_g: Optional[float] = None
    sat_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    packaging_material: Optional[str] = None
    ingredients: List[str]