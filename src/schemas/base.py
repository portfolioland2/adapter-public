from pydantic import BaseModel
from starter_dto.helpers import to_true_camel


class Base(BaseModel):
    class Config:
        alias_generator = to_true_camel
        allow_population_by_field_name = True
