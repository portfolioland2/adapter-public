from pydantic import BaseModel


class ModifierGroupUpdate(BaseModel):
    id: int
    pos_id: str
    min_amount: int
    max_amount: int
    modifier_external_ids: str
