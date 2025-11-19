# services/product_normalization_service.py

from models.dtos import (
    ProductDTO, RawProductAPIDTO
)
# services/product_normalization_service.py

class FoodNormalizationService:
    def normalize(self, raw_data: RawProductAPIDTO) -> ProductDTO:
        """
        API에서 가져온 데이터를 분석 모듈이 사용할 ProductDTO로 정규화
        """
        
        # 1. 원재료명(ingredients_raw) 텍스트 -> List[str] 변환
        ingredients_list = (raw_data.ingredients_raw or "").split(',')
        
        "그외 값들 전부 정규화 예정"

        
        # 5. 최종 ProductDTO 반환
        return ProductDTO(
            product_code=raw_data.barcode,
            name=raw_data.name,
            #요청한 모든 필드 매핑해야함

        )