from fastapi import APIRouter, Depends
from models.dtos import UserAuthRequest, AuthResponse
from services.user_service import UserService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/signup", response_model=AuthResponse, summary="회원가입")
def signup(
    request: UserAuthRequest,
    service: UserService = Depends(UserService)
):
    return service.signup(request)

@router.post("/login", response_model=AuthResponse, summary="로그인")
def login(
    request: UserAuthRequest,
    service: UserService = Depends(UserService)
):
    return service.login(request)