from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# Модели данных (SQLAlchemy)
class ParcelType(Base):
    __tablename__ = "parcel_types"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    parcels = relationship("Parcel", back_populates="parcel_type")


class Parcel(Base):
    __tablename__ = "parcels"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False)  # Для отслеживания пользователя
    name = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    parcel_type_id = Column(Integer, ForeignKey("parcel_types.id"))
    content_value = Column(Float, nullable=False)
    delivery_cost = Column(Float, nullable=True)

    parcel_type = relationship("ParcelType", back_populates="parcels")