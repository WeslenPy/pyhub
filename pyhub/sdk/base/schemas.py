from pydantic import BaseModel
from typing import Optional, List, Dict, Union


class Balance(BaseModel):
    amount: float
    currency: str = "RUB"  # Default for most of these APIs


class NumberActivation(BaseModel):
    activation_id: str
    phone_number: str
    service: str
    cost: Optional[float] = None


class ActivationStatus(BaseModel):
    status: str
    code: Optional[str] = None
    full_text: Optional[str] = None


class ServicePrice(BaseModel):
    service: str
    cost: Union[float, List[float]]
    min_price: float
    max_price: float
    count: int


class CountryPrices(BaseModel):
    country_id: int
    services: Dict[str, ServicePrice]
