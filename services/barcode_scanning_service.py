# services/barcode_scanning_service.py
import io
from pyzbar.pyzbar import decode
from PIL import Image
from fastapi import HTTPException
from models.dtos import BarcodeScanResult 

class BarcodeScanningService:
    def __init__(self):
        pass

    def scan_image_to_barcode(self, image_bytes: bytes) -> BarcodeScanResult:
        """
        라우터로부터 받은 이미지 바이트(bytes)를 스캔하여
        바코드 번호와 타입을 담은 DTO를 반환합니다.
        
        로직 관련 예외처리(e.g., 바코드 없음)는 여기서 담당합니다.
        """
        try:
            # 1. Pillow를 사용하여 바이트 데이터를 이미지로 열기
            img = Image.open(io.BytesIO(image_bytes))
            
            # 2. pyzbar로 바코드 디코딩
            barcodes = decode(img)
            
            if not barcodes:
                raise HTTPException(status_code=404, detail="이미지에서 바코드를 찾을 수 없습니다.")

            # 3. 첫 번째 결과 사용
            first_barcode = barcodes[0]
            barcode_data = first_barcode.data.decode("utf-8")
            barcode_type = first_barcode.type
            
            # 4. DTO에 담아 반환
            return BarcodeScanResult(barcode=barcode_data, type=barcode_type)
        
        except HTTPException as e:
            # 직접 발생시킨 HTTP 예외는 그대로 다시 발생시킴
            raise e
        except Exception as e:
            # Pillow가 이미지를 열지 못하는 등(e.g., 손상된 파일)
            # 예측하지 못한 시스템 오류는 500
            raise HTTPException(status_code=500, detail=f"이미지 처리 중 오류 발생: {str(e)}")