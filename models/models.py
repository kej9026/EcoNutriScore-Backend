#models/models.py
from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, Text, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

# =========================================================
# 1. 사용자 (users)
# =========================================================
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    login_id = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 유저 지우면 스캔 기록도 같이 삭제
    scan_histories = relationship("ScanHistory", back_populates="user", cascade="all, delete-orphan")

# =========================================================
# 2. 제품 마스터 (foods)
# =========================================================
class Food(Base):
    __tablename__ = "foods"

    food_id = Column(Integer, primary_key=True, autoincrement=True)
    barcode = Column(String(50), unique=True, nullable=False) 
    prdlst_report_no = Column(String(50))
    name = Column(String(300))
    brand = Column(String(300))
    category_code = Column(String(32))
    category_name = Column(String(100))
    image_url = Column(String(1000))
    base_nutrition_score = Column(Float, default=0.0)
    base_packaging_score = Column(Float, default=0.0)
    base_additives_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Food를 지우면 영양, 포장, 원재료 정보도 같이 삭제됨
    nutrition = relationship("NutritionFact", back_populates="food", uselist=False, cascade="all, delete-orphan")
    recycling = relationship("RecyclingInfo", back_populates="food", uselist=False, cascade="all, delete-orphan")
    ingredients = relationship("Ingredient", back_populates="food", cascade="all, delete-orphan")
    
    scan_histories = relationship("ScanHistory", back_populates="food", cascade="all, delete-orphan")

# =========================================================
# 3. 영양성분 (nutrition_facts)
# =========================================================
class NutritionFact(Base):
    __tablename__ = "nutrition_facts"

    nf_id = Column(Integer, primary_key=True, autoincrement=True)

    barcode = Column(String(50), ForeignKey("foods.barcode", ondelete="CASCADE"), unique=True)
    
    serving_size = Column(String(50))
    sodium_mg = Column(Integer)
    sugar_g = Column(Integer)
    sat_fat_g = Column(Float)
    trans_fat_g = Column(Float)
    additives_cnt = Column(Integer)

    food = relationship("Food", back_populates="nutrition")

# =========================================================
# 4. 재활용 정보 (recycling_info)
# =========================================================
class RecyclingInfo(Base):
    __tablename__ = "recycling_info"

    recy_id = Column(Integer, primary_key=True, autoincrement=True)
    # [수정] ondelete="CASCADE" 추가
    barcode = Column(String(50), ForeignKey("foods.barcode", ondelete="CASCADE"), unique=True)
    
    recycling_rate = Column(Float)
    material = Column(String(50)) 

    food = relationship("Food", back_populates="recycling")

# =========================================================
# 5. 원재료 (ingredients)
# =========================================================
class Ingredient(Base):
    __tablename__ = "ingredients"

    ing_id = Column(Integer, primary_key=True, autoincrement=True)
    # [수정] ondelete="CASCADE" 추가
    barcode = Column(String(50), ForeignKey("foods.barcode", ondelete="CASCADE"))
    name = Column(String(300))
    raw_materials = Column(Text, nullable=True)
    additives_list = Column(Text, nullable=True)
    food = relationship("Food", back_populates="ingredients")

# =========================================================
# 6. 스캔 기록 (scan_history)
# =========================================================
class ScanHistory(Base):
    __tablename__ = "scan_history"

    scan_id = Column(Integer, primary_key=True, autoincrement=True)
    # [수정] ondelete="CASCADE" 추가 (유저나 음식이 삭제되면 기록도 삭제)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.food_id", ondelete="CASCADE"), nullable=False)

    # 가중치
    nutrition_weight = Column(DECIMAL(4, 2), default=1.0)
    packaging_weight = Column(DECIMAL(4, 2), default=1.0)
    additives_weight = Column(DECIMAL(4, 2), default=1.0)

    # 결과 점수
    nutrition_score = Column(DECIMAL(7, 2))
    packaging_score = Column(DECIMAL(7, 2))
    additives_score = Column(DECIMAL(7, 2))
    score_total = Column(DECIMAL(8, 2))
    grade = Column(String(2))

    scanned_at = Column(DateTime(timezone=True), server_default=func.now())

    # [수정] back_populates 연결
    food = relationship("Food", back_populates="scan_histories")
    user = relationship("User", back_populates="scan_histories")

class Additive(Base):
    __tablename__ = "additives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)