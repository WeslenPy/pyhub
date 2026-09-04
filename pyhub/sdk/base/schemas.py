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
    min_price_disp:float
    max_price_disp:float
    count_max_price:int
    count_min_price:int
    count: int


class CountryPrices(BaseModel):
    country_id: int
    services: Dict[str, ServicePrice]


class Service(BaseModel):
    code: str
    name: str


class Country(BaseModel):
    id: int
    rus: str
    eng: str
    chn: Optional[str] = None
    visible: int
    retry: int


class ReactivationDuration(BaseModel):
    unit: str
    value: int


class ReactivationOption(BaseModel):
    price: float
    duration: ReactivationDuration


class ReactivationResult(BaseModel):
    activation_id: str
    phone_number: str
    activation_cost: Optional[float] = None
    currency: Optional[int] = None
    country_code: Optional[int] = None
    country_phone_code: Optional[float] = None
    can_get_another_sms: Optional[bool] = None
    activation_time: Optional[str] = None
    activation_end_time: Optional[str] = None
    activation_operator: Optional[str] = None
    verification_type: Optional[str] = None
    subtype: Optional[int] = None
    service_code: Optional[str] = None
    status: Optional[int] = None
