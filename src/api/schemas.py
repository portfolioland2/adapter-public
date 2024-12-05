from pydantic import BaseModel
from starter_dto.helpers import to_true_camel
from starter_dto.pos import CreateOrder


class OrderWithCtx(CreateOrder):
    ctx: dict


class OrderCreatedApi(BaseModel):
    order_id: str

    class Config:
        alias_generator = to_true_camel
        allow_population_by_field_name = True
