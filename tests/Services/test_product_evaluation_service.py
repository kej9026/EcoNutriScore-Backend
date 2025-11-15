import pytest
from unittest.mock import Mock, MagicMock

# --- 테스트 대상(SUT) 및 의존성 임포트 ---
# (경로는 실제 프로젝트 구조에 맞게 조정해야 할 수 있습니다)
from services.product_evaluation_service import ProductEvaluationService
from services.score_retrieval_service import ScoreRetrievalService
from services.product_pipeline_service import ProductPipelineService

# --- 테스트용 가짜(Fake) DTO 데이터 ---
# (dtos.py의 실제 DTO 구조를 기반으로 만듭니다)
from models.dtos import AnalysisScoresDTO, PackagingScore, AdditivesScore, NutritionScore

FAKE_CACHED_SCORES = AnalysisScoresDTO(
    packaging=PackagingScore(score=90, details=[]),
    additives=AdditivesScore(score=80, risks=[]),
    nutrition=NutritionScore(score=70, highlights=[]),
    name="[캐시]가짜상품",
    image_url="http://sdffsdfake.com/cached.jpg",
    category_code="C001"
)

FAKE_PIPELINE_SCORES = AnalysisScoresDTO(
    packaging=PackagingScore(score=50, details=[]),
    additives=AdditivesScore(score=40, risks=[]),
    nutrition=NutritionScore(score=30, highlights=[]),
    name="[신규]가짜상품",
    image_url="http://sdffsdfake.com/new.jpg",
    category_code="C002"
)

TEST_BARCODE_FAST = "11111111" # Fast Path (캐시 O) 테스트용
TEST_BARCODE_SLOW = "22222222" # Slow Path (캐시 X) 테스트용


# --- 테스트 픽스처(Fixture) 설정 ---

@pytest.fixture
def mock_retrieval_service() -> MagicMock:
    """'창고 담당'의 가짜(Mock) 객체를 생성합니다."""
    # MagicMock은 __init__ 없이도 사용 가능한 Mock입니다.
    return MagicMock(spec=ScoreRetrievalService)

@pytest.fixture
def mock_pipeline_service() -> MagicMock:
    """'신규 요리사'의 가짜(Mock) 객체를 생성합니다."""
    return MagicMock(spec=ProductPipelineService)

@pytest.fixture
def evaluation_service(
    mock_retrieval_service: MagicMock,
    mock_pipeline_service: MagicMock
) -> ProductEvaluationService:
    """
    테스트 대상(SUT)인 '총괄 셰프'를 생성합니다.
    이때, 실제 서비스 대신 '가짜' 서비스 객체들을 주입(Inject)합니다.
    """
    return ProductEvaluationService(
        retriever=mock_retrieval_service,
        pipeline=mock_pipeline_service
    )

# --- 테스트 케이스 ---

def test_get_analysis_scores_fast_path(
    evaluation_service: ProductEvaluationService,
    mock_retrieval_service: MagicMock,
    mock_pipeline_service: MagicMock
):
    """
    [시나리오 1] "재고 있음" (Fast Path)
    ScoreRetrievalService가 점수를 반환했을 때,
    PipelineService가 호출되지 않고 즉시 해당 점수가 반환되는지 검증합니다.
    """
    # --- [Arrange] 준비 ---
    # '창고 담당(retriever)'이 FAKE_CACHED_SCORES를 반환하도록 '연기' 설정
    mock_retrieval_service.get_existing_scores.return_value = FAKE_CACHED_SCORES

    # --- [Act] 실행 ---
    result = evaluation_service.get_analysis_scores(TEST_BARCODE_FAST)

    # --- [Assert] 검증 ---
    # 1. 반환된 결과가 '캐시된' 점수와 일치하는가?
    assert result == FAKE_CACHED_SCORES
    assert result.name == "[캐시]가짜상품" # 명시적 확인
    
    # 2. '창고 담당'이 정확히 1번, 올바른 바코드로 호출되었는가?
    mock_retrieval_service.get_existing_scores.assert_called_once_with(TEST_BARCODE_FAST)
    
    # 3. [중요] '신규 요리사(pipeline)'는 '절대로' 호출되지 않았는가?
    mock_pipeline_service.create_and_save_new_scores.assert_not_called()

def test_get_analysis_scores_slow_path(
    evaluation_service: ProductEvaluationService,
    mock_retrieval_service: MagicMock,
    mock_pipeline_service: MagicMock
):
    """
    [시나리오 2] "재고 없음" (Slow Path)
    ScoreRetrievalService가 None을 반환했을 때,
    PipelineService가 호출되고, 그 결과가 반환되는지 검증합니다.
    """
    # --- [Arrange] 준비 ---
    # 1. '창고 담당'은 "재고 없음(None)"을 반환하도록 '연기' 설정
    mock_retrieval_service.get_existing_scores.return_value = None
    
    # 2. '신규 요리사'는 FAKE_PIPELINE_SCORES를 반환하도록 '연기' 설정
    mock_pipeline_service.create_and_save_new_scores.return_value = FAKE_PIPELINE_SCORES

    # --- [Act] 실행 ---
    result = evaluation_service.get_analysis_scores(TEST_BARCODE_SLOW)

    # --- [Assert] 검증 ---
    # 1. 반환된 결과가 '신규 생성된(pipeline)' 점수와 일치하는가?
    assert result == FAKE_PIPELINE_SCORES
    assert result.name == "[신규]가짜상품" # 명시적 확인
    
    # 2. '창고 담당'이 정확히 1번, 올바른 바코드로 호출되었는가?
    mock_retrieval_service.get_existing_scores.assert_called_once_with(TEST_BARCODE_SLOW)
    
    # 3. [중요] '신규 요리사'가 정확히 1번, 올바른 바코드로 호출되었는가?
    mock_pipeline_service.create_and_save_new_scores.assert_called_once_with(TEST_BARCODE_SLOW)