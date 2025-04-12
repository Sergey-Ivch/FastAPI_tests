from typing import Optional

from pydantic import BaseModel, Field, validator


class ParcelBase(BaseModel):
    name: str = Field(..., title="Название посылки")
    weight: float = Field(..., title="Вес посылки (кг)")
    parcel_type_id: int = Field(..., title="ID типа посылки")
    content_value: float = Field(..., title="Стоимость содержимого посылки (USD)")

    @validator("weight")
    def weight_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("Вес должен быть положительным числом")
        return value

    @validator("content_value")
    def content_value_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("Стоимость содержимого должна быть положительным числом")
        return value


class ParcelCreate(ParcelBase):
    pass


class ParcelRead(ParcelBase):
    id: int
    delivery_cost: Optional[float] = None
    parcel_type: str
    class Config:
        from_attributes = True

class ParcelTypeRead(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True