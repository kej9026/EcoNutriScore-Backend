from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from repositories.user_repository import UserRepository
from models.dtos import UserAuthRequest, AuthResponse

# 비밀번호 해싱 설정 (Bcrypt 사용)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class UserService:
    def __init__(self, repo: UserRepository = Depends(UserRepository)):
        self.repo = repo

    def signup(self, req: UserAuthRequest) -> AuthResponse:
        # 1. 아이디 중복 체크
        if self.repo.get_user_by_login_id(req.login_id):
            raise HTTPException(status_code=400, detail="이미 사용 중인 아이디입니다.")

        # 2. 비밀번호 길이 체크
        if len(req.password) < 8:
            raise HTTPException(status_code=400, detail="비밀번호는 최소 8자리 이상이어야 합니다.")

        print(f"👉 [DEBUG] 받은 비번: {req.password}")
        print(f"👉 [DEBUG] 비번 길이: {len(req.password)}") # 10이어야 정상
        
        # 3. 비밀번호 해싱 (암호화)
        hashed_pw = pwd_context.hash(req.password)

        # 4. 저장
        user = self.repo.create_user(req.login_id, hashed_pw)

        return AuthResponse(
            user_id=user.user_id,
            login_id=user.login_id,
            success=True,
            message="회원가입 성공"
        )

    def login(self, req: UserAuthRequest) -> AuthResponse:
        # 1. 아이디로 찾기
        user = self.repo.get_user_by_login_id(req.login_id)
        if not user:
            # 보안상 아이디/비번 틀림 메시지는 통일하는 게 좋음
            raise HTTPException(status_code=400, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

        # 2. 비밀번호 검증 (입력받은 비번 vs DB 해시)
        if not pwd_context.verify(req.password, user.password_hash):
            raise HTTPException(status_code=400, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

        return AuthResponse(
            user_id=user.user_id,
            login_id=user.login_id,
            success=True,
            message="로그인 성공"
        )