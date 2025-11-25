# models/dtos.py
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
# ===================================================================
# 0. 공통 타입 정의
# ===================================================================
Grade = Literal['A', 'B', 'C', 'D', 'E']

# ===================================================================
# 1. [0단계] 바코드 스캔 결과 (Barcode Service)
# ===================================================================
class BarcodeScanResult(BaseModel):
    """이미지 업로드 시 바코드 인식 결과"""
    barcode: str
    type: str = "unknown" # e.g., EAN-13

# ===================================================================
# 2. [1단계 입력] 외부 API/DB 원본 데이터 (Repository)
# ===================================================================
class RawProductAPIDTO(BaseModel):
    """
    [Repository -> Service]
    식약처 API의 지저분한 필드명을 그대로 받아주는 DTO
    """
    barcode: str
    name: str                # PRDLST_NM -> name
    report_no: Optional[str] # PRDLST_REPORT_NO -> report_no
    image_url: Optional[str] = None # IMG_URL -> image_url
    category_code: Optional[str]  # PRDLST_DCNM -> category
    category_name: Optional[str] = None
    brand: Optional[str]     # BSSH_NM -> brand
    base_nutrition_score: float = 0.0
    base_packaging_score: float = 0.0
    base_additives_score: float = 0.0
    # 영양 정보 (문자열로 올 수도 있어서 유연하게)
    serving_size: Optional[str] = None
    sodium_mg: Optional[str]    = None
    sugar_g: Optional[str]      = None
    sat_fat_g: Optional[str]    = None
    trans_fat_g: Optional[str]  = None
    
    # 포장/첨가물
    packaging_material: Optional[str] = None
    additives_cnt: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, extra='ignore')


# ===================================================================
# 3. [1단계 출력] 분석 결과 (Service -> Frontend)
# ===================================================================
# 프론트엔드가 그래프를 그리거나 상세 정보를 보여줄 때 사용

class NutritionDetail(BaseModel):
    """영양 점수 상세 (100ml 기준 환산값 포함)"""
    score: float
    sodium_mg: float
    sugar_g: float
    sat_fat_g: float
    trans_fat_g: float
    serving_ml: Optional[float] = None

class PackagingDetail(BaseModel):
    """포장재 점수 상세"""
    score: float
    material: str       # 정규화된 재질명 (예: "PET", "유리")   
    raw_material: Optional[str] = None # 원본 문자열

class AdditivesDetail(BaseModel):
    """첨가물 점수 상세"""
    score: float
    count: int
    risk_level: str = "Unknown" # 필요시 사용

class AnalysisScoresDTO(BaseModel):
    """
    [API 1단계 응답] /products/analysis/{barcode}
    3대 분석 점수와 제품 기본 정보를 담고 있음
    """
    barcode: str
    name: str
    report_no: Optional[str] = None
    image_url: Optional[str] = None
    
    # 3대 분석 결과 (객체로 구조화)
    nutrition: NutritionDetail
    packaging: PackagingDetail
    additives: AdditivesDetail
    
    model_config = ConfigDict(from_attributes=True)


# ===================================================================
# 4. [2단계 입력] 가중치 및 최종 계산 요청 (Frontend -> API)
# ===================================================================
class UserPrioritiesDTO(BaseModel):
    """
    사용자가 슬라이더로 설정한 중요도(양수: 오른쪽이 더 중요/음수: 왼쪽이 더 중요)
    """
    pkg_vs_add: int = 1
    pkg_vs_nut: int = 1
    add_vs_nut: int = 1

class GradeCalculationRequest(BaseModel):
    """
    [API 2단계 요청] /foods/calculate-grade
    1단계에서 받은 '점수 데이터' + 사용자가 설정한 '가중치'를 되돌려 보냄
    """
    scores: AnalysisScoresDTO
    priorities: UserPrioritiesDTO


# ===================================================================
# 5. [2단계 출력] 최종 등급 결과 (API -> Frontend)
# ===================================================================
class UserWeightsDTO(BaseModel):
    """
    계산된 실제 가중치 (0.33, 0.5 등)
    - 프론트엔드가 그래프 그릴 때 사용
    - 추천 API 호출할 때 다시 사용
    """
    nutrition_weight: float
    packaging_weight: float
    additives_weight: float

class GradeResult(BaseModel):
    """
    [API 2단계 응답] 최종 계산 결과
    """
    scan_id: Optional[int] = None # DB 저장 시 생성된 ID
    user_id: int
    food_id: Optional[int] = None
    
    name: str
    grade: Grade
    total_score: float
    
    # 어떤 가중치로 계산했는지 확인용
    weights: UserWeightsDTO
    
    # 상세 점수 (그래프용)
    nutrition_score: float
    packaging_score: float
    additives_score: float
class RecommendationRequestDTO(BaseModel):
    """
    프론트엔드가 가지고 있는 정보를 그대로 던져줌
    """
    report_no: str          # 카테고리 찾기용
    total_score: float      # 기준 점수
    weights: UserWeightsDTO # 가중치
class RecommendationResultDTO(BaseModel):
    """
    추천된 제품의 정보 + 계산된 점수/등급
    """
    barcode: str
    name: str
    image_url: Optional[str] = None
    brand: Optional[str] = None
    
    # 핵심 정보
    total_score: float  # 가중치가 반영된 총점
    grade: Grade        # A, B, C... 등급

    nutrition_score: float
    packaging_score: float
    additives_score: float

    model_config = ConfigDict(from_attributes=True)

# ===================================================================
# 6. [히스토리] 스캔 기록 목록 (History API)
# ===================================================================
class ScanHistoryDTO(BaseModel):
    """
    [API] /history/me 목록 조회용
    """
    scan_id: int
    product_name: str
    image_url: Optional[str] = None
    grade: Grade
    total_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# [회원가입/로그인 요청]
class UserAuthRequest(BaseModel):
    login_id: str
    password: str

# [회원가입/로그인 응답]
class AuthResponse(BaseModel):
    user_id: int
    login_id: str
    success: bool
    message: Optional[str] = None