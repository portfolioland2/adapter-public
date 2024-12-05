from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models import Discount


class DiscountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_discounts(self, client_id: int) -> Sequence[Discount]:
        return self.session.scalars(select(Discount).where(Discount.client_id == client_id)).all()

    def create_discount(self, client_id: int, pos_id: int, starter_id: str) -> None:
        discount = Discount(client_id=client_id, pos_id=pos_id, starter_id=starter_id)
        self.session.add(discount)

    def clear_discounts(self, client_id: int) -> None:
        self.session.query(Discount).where(Discount.client_id == client_id).delete()
