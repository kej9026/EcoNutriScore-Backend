import pytest
from fastapi import HTTPException
from pathlib import Path

# 테스트할 서비스 임포트
from services.barcode_scanning_service import BarcodeScanningService
# 서비스가 반환할 DTO 임포트
from models.dtos import BarcodeScanResult

# -------------------------------------------------------------------
# 테스트 설정 및 픽스처(Fixture)
# -------------------------------------------------------------------

# 현재 테스트 파일의 위치를 기준으로 /tests/test_assets/ 경로 설정
BASE_DIR = Path(__file__).parent.parent
ASSETS_DIR = BASE_DIR / "test_assets"

# 'scanner_service' 픽스처:
# 테스트 함수들이 서비스 인스턴스를 주입받아 사용할 수 있게 함
# scope="module": 테스트 모듈(파일) 당 딱 한 번만 서비스 객체를 생성
@pytest.fixture(scope="module")
def scanner_service():
    """BarcodeScanningService의 인스턴스를 생성합니다."""
    return BarcodeScanningService()

# 'valid_barcode_bytes' 픽스처:
# 테스트용 QR코드 이미지 파일을 'bytes'로 읽어서 준비
@pytest.fixture(scope="module")
def valid_barcode_bytes():
    """유효한 바코드 이미지(QR 코드)의 바이트를 반환합니다."""
    file_path = ASSETS_DIR / "valid_barcode.jpg"
    if not file_path.exists():
        pytest.fail("테스트 파일 'valid_barcode.png'가 'tests/test_assets'에 없습니다.")
    
    with open(file_path, "rb") as f:
        return f.read()

# 'blank_image_bytes' 픽스처:
# 텅 빈 이미지 파일을 'bytes'로 읽어서 준비
@pytest.fixture(scope="module")
def blank_image_bytes():
    """바코드가 없는 텅 빈 이미지의 바이트를 반환합니다."""
    file_path = ASSETS_DIR / "blank_image.jpg"
    if not file_path.exists():
        pytest.fail("테스트 파일 'blank_image.jpg'가 'tests/test_assets'에 없습니다.")
        
    with open(file_path, "rb") as f:
        return f.read()

# 'corrupt_file_bytes' 픽스처:
# 이미지가 아닌 텍스트 파일을 'bytes'로 읽어서 준비
@pytest.fixture(scope="module")
def corrupt_file_bytes():
    """이미지 파일이 아닌(손상된) 텍스트 파일의 바이트를 반환합니다."""
    file_path = ASSETS_DIR / "not_an_image.txt"
    if not file_path.exists():
        pytest.fail("테스트 파일 'not_an_image.txt'가 'tests/test_assets'에 없습니다.")
        
    with open(file_path, "rb") as f:
        return f.read()

# -------------------------------------------------------------------
# 테스트 케이스
# -------------------------------------------------------------------

def test_scan_barcode_success(scanner_service, valid_barcode_bytes):
    """
    [성공 케이스]
    유효한 QR 코드 이미지를 스캔하고, 
    정확한 바코드 데이터와 타입을 반환하는지 테스트합니다.
    """
    # 1. 실행 (When)
    result = scanner_service.scan_image_to_barcode(valid_barcode_bytes)
    
    # 2. 검증 (Then)
    assert isinstance(result, BarcodeScanResult)
    # 1단계에서 "capstone-test-barcode"로 QR코드를 만들었다고 가정
    assert result.barcode == "9002490254834"
    assert result.type == "EAN13"


def test_scan_barcode_not_found(scanner_service, blank_image_bytes):
    """
    [실패 케이스]
    텅 빈 이미지를 스캔했을 때, 
    HTTPException 404를 발생하는지 테스트합니다.
    """
    # 1. 실행 (When)
    with pytest.raises(HTTPException) as exc_info:
        scanner_service.scan_image_to_barcode(blank_image_bytes)
        
    # 2. 검증 (Then)
    assert exc_info.value.status_code == 404
    assert "찾을 수 없습니다" in exc_info.value.detail


def test_scan_corrupt_file_error(scanner_service, corrupt_file_bytes):
    """
    [예외 케이스]
    이미지가 아닌 파일(e.g., txt)을 처리하려 할 때,
    Pillow(PIL)가 오류를 내고 서비스가 이를 500 에러로 처리하는지 테스트합니다.
    """
    # 1. 실행 (When)
    with pytest.raises(HTTPException) as exc_info:
        scanner_service.scan_image_to_barcode(corrupt_file_bytes)
        
    # 2. 검증 (Then)
    assert exc_info.value.status_code == 500
    assert "이미지 처리 중 오류" in exc_info.value.detail