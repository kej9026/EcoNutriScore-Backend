from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db
from models.models import User

class UserRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def get_user_by_login_id(self, login_id: str):
        """아이디로 유저 찾기"""
        return self.db.query(User).filter(User.login_id == login_id).first()

    def create_user(self, login_id: str, password_hash: str) -> User:
        """유저 생성 (비번은 이미 해시된 상태로 받아옴)"""
        new_user = User(
            login_id=login_id,
            password_hash=password_hash
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user