from typing import Optional

from pydantic import validator
from pydantic.main import BaseModel

from src.config import settings


class Client(BaseModel):
    client_id: str
    client_secret: str
    api_key: str
    project_name: Optional[str] = None
    currency_code: Optional[str] = settings.RUBLE_CURRENCY_CODE
    discount_id: Optional[int] = None
    get_modifier_max_amount: Optional[bool] = False
    is_use_loyalty: bool = False
    is_split_order_items_for_keeper: bool = False
    is_use_modifier_external_id: bool = False
    is_use_discounts_as_variable: bool = False
    is_use_global_modifier_complex: bool = False
    is_skip_update_order_payment_status: bool = False

    @validator("currency_code")
    def not_none_currency_code(cls, v: Optional[str]) -> str:
        return v if v else settings.RUBLE_CURRENCY_CODE
