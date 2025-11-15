from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Literal

# ===================================================================
# 0. 공통 타입 및 API 입출력 DTO
# ===================================================================
# API 라우터(routers)와 클라이언트(앱) 간의
# 최초 요청과 최종 응답을 정의
# ===================================================================

Grade = Literal['A', 'B', 'C', 'D', 'E']
"""최종 점수에 따라 부여되는 등급을 A, B, C, D, E로 한정"""

class BarcodeScanResult(BaseModel):
    """
    [데이터: 바코드 스캔 결과]
    - '누가 만드나?': BarcodeScanningService (서버 내부)
    - '누가 쓰나?': 
        1. /scan-barcode-image API가 클라이언트에게 응답할 때
        2. 클라이언트가 이 정보를 BarcodeScanRequest에 담아 /analyze API에 요청할 때
    """
    barcode: str
    type: str  # 예: "image_scan", "text_input"

class BarcodeScanRequest(BaseModel):
    """
    [API 1 요청] /products/analyze
    - '누가 만드나?': 클라이언트 (앱)
    - '누가 쓰나?': /analyze API 라우터
    - '무엇을 담나?': 클라이언트가 스캔한 BarcodeScanResult 정보
    """
    scan_result: BarcodeScanResult

class GradeResult(BaseModel):
    """
    [API 2 응답] /products/calculate-grade
    - '누가 만드나?': TotalScoreService (최종 점수 계산 완료 후)
    - '누가 쓰나?': /calculate-grade API 라우터가 클라이언트에게 보내는 최종 응답
    """
    total_score: float
    grade: Grade
    name: str
    image_url: Optional[str] = None

# ===================================================================
# 1. 정규화 서비스 (NormalizationService) 입출력
# ===================================================================
# 이 섹션의 DTO는 '파이프라인 1단계: 데이터 정규화'의 
# '입력(Raw)'과 '출력(ProductDTO)'을 정의합니다.
# ===================================================================

class RawProductAPIDTO(BaseModel):
    """
    [데이터: 외부 API 원본]
    - '누가 만드나?': ProductRepository (식약처 등 외부 API 조회 직후)
    - '누가 쓰나?': ProductNormalizationService (정규화 서비스의 입력)
    - '특징': 
        - 필드명이나 데이터 구조가 API 제공처에 따라 제각각이고 지저분합니다.
        - (예: "PRDLST_NM", "raw_materials_text")
    """
    barcode: str
    name: str
    raw_materials: Optional[str] = None
    packaging_info: Optional[str] = None
    # ... (API가 주는 다른 모든 원본 필드) ...

    model_config = ConfigDict(
        from_attributes=True, # ORM 객체 등에서 변환 허용
        extra='ignore'      # DTO에 정의되지 않은 필드는 무시
    )

class ProductDTO(BaseModel):
    """
    [데이터: 표준 제품 규격]
    - '누가 만드나?': ProductNormalizationService (정규화 서비스의 출력)
    - '누가 쓰나?': 
        1. PackagingAnalysisService
        2. AdditivesAnalysisService
        3. NutritionAnalysisService
    - '특징': 
        - `RawProductAPIDTO`를 깨끗하게 정제한 표준 데이터입니다.
        - 모든 3대 분석 서비스(포장재, 첨가물, 영양)는 
        - 오직 이 DTO 하나만을 입력으로 받아 분석을 수행합니다.
    """
    # 기본 정보
    barcode: str
    name: str
    report_no: Optional[str] = None
    image_url: Optional[str] = None
    category_code: Optional[str] = None
    
    # 영양 정보 (-> NutritionAnalysisService 입력)
    serving_size: Optional[str] = None
    sodium_mg: Optional[float] = None
    sugar_g: Optional[float] = None
    sat_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    
    # 포장재 정보 (-> PackagingAnalysisService 입력)
    packaging_material: Optional[str] = None # 예: "용기:PET,뚜껑:PP"
    
    # 첨가물 정보 (-> AdditivesAnalysisService 입력)
    ingredients: List[str] = [] # 정규화된 원재료명 리스트

# ===================================================================
# 2. 분석 서비스 (Analysis) 입출력
# ===================================================================
# 이 섹션의 DTO는 파이프라인 2단계: 3대 분석의
# 출력(Score)들과, 그 출력들을 하나로 묶은 결과물(AnalysisScoresDTO)을 정의
# ===================================================================

class PackagingScore(BaseModel):
    """
    [분석 결과 1: 포장재]
    - '누가 만드나?': PackagingAnalysisService
    - '누가 쓰나?': AnalysisScoresDTO (아래 DTO의 packaging 필드)
    """
    score: int
    details: List[dict] # 예: [{'material': 'PET', 'score': 85}, ...]

class AdditivesScore(BaseModel):
    """
    [분석 결과 2: 첨가물]
    - '누가 만드나?': AdditivesAnalysisService
    - '누가 쓰나?': AnalysisScoresDTO (아래 DTO의 additives 필드)
    """
    score: int
    risks: List[dict]   # 예: [{'name': '아스파탐', 'level': 3}, ...]

class NutritionScore(BaseModel):
    """
    [분석 결과 3: 영양]
    - '누가 만드나?': NutritionAnalysisService
    - '누가 쓰나?': AnalysisScoresDTO (아래 DTO의 nutrition 필드)
    """
    score: int          # (세부 항목을 조합한 영양 종합 점수)
    highlights: List[dict] # 예: [{'nutrient': '나트륨', 'level': '높음'}, ...]

class AnalysisScoresDTO(BaseModel):
    """
    [API 1 응답] /products/analyze
    - '누가 만드나?': ProductPipelineService (3대 분석 결과를 취합하여)
    - '누가 쓰나?': 
        1. [API 1 응답] /analyze 라우터가 클라이언트에게 응답 (1단계 끝)
        2. [캐시/DB] ProductRepository가 이 DTO를 DB/캐시에 저장
        3. [API 2 요청] 클라이언트가 이 DTO를 GradeCalculationRequest에 담아 재전송
    """
    packaging: PackagingScore
    additives: AdditivesScore
    nutrition: NutritionScore
    name: str # (ProductDTO에서 가져온 기본 정보)
    image_url: Optional[str] = None
    category_code: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True # DB 모델(ORM)에서 Pydantic 모델로 바로 변환 허용
    )

# ===================================================================
# 3. 총점 서비스 (TotalScore) 입출력
# ===================================================================
# 이 섹션의 DTO는 '파이프라인 3단계: 가중치 적용'의
# '입력(Request)'을 정의합니다. ('출력'은 Section 0의 GradeResult)
# ===================================================================

class UserPrioritiesDTO(BaseModel):
    """
    [데이터: 사용자 가중치]
    - '누가 만드나?': 클라이언트 (앱 사용자가 AHP 가중치 입력)
    - '누가 쓰나?': 
        1. GradeCalculationRequest (아래 DTO의 priorities 필드)
        2. TotalScoreService (최종 점수 계산기의 입력)
    """
    pkg_vs_add: int
    pkg_vs_nut: int
    add_vs_nut: int

class GradeCalculationRequest(BaseModel):
    """
    [API 2 요청] /products/calculate-grade
    - '누가 만드나?': 클라이언트 (앱)
    - '누가 쓰나?': /calculate-grade API 라우터
    - '무엇을 담나?': 
        1. 'scores': [API 1]에서 받았던 3대 분석 점수(AnalysisScoresDTO)
        2. 'priorities': 사용자가 방금 입력한 가중치(UserPrioritiesDTO)
    """
    scores: AnalysisScoresDTO
    priorities: UserPrioritiesDTO