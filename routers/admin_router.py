# routers/admin_router.py
from fastapi import APIRouter, Depends, Header, HTTPException
from services.admin_service import AdminService
from models.dtos import FoodImageUpdateDTO
import os

router = APIRouter(
    prefix="/admin",
    tags=["Admin Operations"]
)

# 간단한 보안 검사 함수

@router.patch("/foods/{barcode}/image")
def update_product_image(
    barcode: str,
    body: FoodImageUpdateDTO,
    service: AdminService = Depends(AdminService)
):
    """
    [관리자 전용] 제품 이미지 수동 업데이트
    - 구글 드라이브 공유 링크를 넣으면 자동으로 변환
    """
    return service.update_image(barcode, body)