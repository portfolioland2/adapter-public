import hashlib

from pydantic import BaseModel
from starter_dto import pos

from src.schemas.rkeeper import RKeeperModifiers


class DomainModifierSchema(RKeeperModifiers):
    min_amount: int | None
    required: bool

    @property
    def specific_id(self) -> str:
        return f"{self.pos_id}/{self.min_amount}/{self.max_amount}"

    @property
    def specific_external_id(self) -> str:
        return f"{self.external_id}/{self.min_amount}/{self.max_amount}"


class DomainModifierGroupSchema(BaseModel):
    pos_id: str
    min_amount: int
    max_amount: int
    modifiers: list[DomainModifierSchema]
    name: str | None
    required: bool

    @property
    def specific_id(self) -> str:
        return f"{self.pos_id}/{self.min_amount}/{self.max_amount}"

    @property
    def modifier_external_ids(self) -> str:
        _modifiers_external_ids = sorted([modifier.external_id for modifier in self.modifiers])
        return "/".join(_modifiers_external_ids)

    @property
    def hashed_id(self) -> str:
        _modifier_data_to_hash = self.modifier_external_ids + f"{self.min_amount}/{self.max_amount}"

        return hashlib.md5(_modifier_data_to_hash.encode("utf-8")).hexdigest()
