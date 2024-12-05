from pydantic import BaseModel
from starter_dto.pos.base import ObjectOut


class ClientUpdate(BaseModel):
    currency_code: str | None = None
    discount_id: int | None = None
    is_use_loyalty: bool = False
    is_split_order_items_for_keeper: bool = False
    is_use_modifier_external_id: bool = False
    is_skip_update_order_payment_status: bool = False
    project_id: int | None = None
    #  TODO: add to next release
    # is_use_discounts_as_variable: bool = False
    # is_use_global_modifier_complex: bool = False
    # get_modifier_max_amount: bool = False


class ClientCreate(ClientUpdate):
    client_id: str
    client_secret: str
    api_key: str


class MealOfferStarterCreated(ObjectOut):
    meal_id: int


class MealStarterCreated(ObjectOut):
    external_id: str
