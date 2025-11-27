# services/admin_service.py
import re
from fastapi import Depends, HTTPException, Header
from repositories.food_repository import FoodRepository
from models.dtos import FoodImageUpdateDTO
import os

class AdminService:
    def __init__(self, repo: FoodRepository = Depends(FoodRepository)):
        self.repo = repo

    def update_image(self, barcode: str, dto: FoodImageUpdateDTO):
        # 1. 링크 변환 (Google Drive -> Direct Link)
        final_url = self._convert_google_drive_link(dto.image_url)
        
        # 2. 리포지토리 호출
        success = self.repo.update_food_image(barcode, final_url)
        
        if not success:
            raise HTTPException(404, "Product not found or update failed")
        
        return {"message": "Image updated successfully", "url": final_url}

    def _convert_google_drive_link(self, url: str) -> str:
        """
        구글 드라이브 공유 링크를 <img> 태그용 링크로 변환
        """
        # 파일 ID 추출 패턴
        # https://drive.google.com/file/d/THIS_IS_FILE_ID/view...
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        
        # 구글 링크가 아니면 그냥 원래 URL 반환 (Imgur 등)
        return url