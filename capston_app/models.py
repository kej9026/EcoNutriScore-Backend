from sqlalchemy import Column, Integer, String, Float
from capston_app.database import Base


class Item(Base):
    __tablename__ = "items"
    id    = Column(Integer, primary_key=True, index=True)
    name  = Column(String(100))
    price = Column(Float)
    #price = Column(Numeric(12, 2))

# 바코드로 저장할 제품 테이블
class Product(Base):
    __tablename__ = "products"
    id         = Column(Integer, primary_key=True, index=True, autoincrement=True)
    barcode    = Column(String(50), unique=True, index=True, nullable=False)
    name       = Column(String(255), nullable=True)      # PRDLST_NM
    company    = Column(String(255), nullable=True)       # BSSH_NM
    expire     = Column(String(100), nullable=True)       # POG_DAYCNT 등