from sqlalchemy import Column, ForeignKey, Integer, String, Float, UniqueConstraint, Numeric
from database import Base


class Item(Base):
    __tablename__ = "items"
    id    = Column(Integer, primary_key=True, index=True)
    name  = Column(String(100))
    price = Column(Numeric(12, 2))

# 바코드로 저장할 제품 테이블
class ProductHaccp(Base):
    __tablename__ = "product_haccp"
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String(50), nullable=False)
    product_name = Column(String(300), nullable=True)
    manufacturer = Column(String(300), nullable=True)
    img_url = Column(String(1000))
    pack_img_url = Column(String(1000))
    meta_img_url = Column(String(1000))

    __table_args__ = (
        UniqueConstraint("barcode", "product_name", name="uq_barcode_product"),
    )
    
class ScanHistory(Base):
    __tablename__ = "scan_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    prdlst_report_no = Column(String, index=True)
    prdlst_nm = Column(String)
    total_score = Column(Integer)
    grade = Column(String(1))
    
    # [신규] 가중치 저장을 위한 컬럼 추가
    pkg_weight = Column(Float)
    add_weight = Column(Float)
    nut_weight = Column(Float)
