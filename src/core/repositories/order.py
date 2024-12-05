from typing import Sequence

from sqlalchemy import update, select
from sqlalchemy.orm import Session

from src.exceptions import ObjectDoesNotExist
from src.models import Order
from src.utils.enums import Entity


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_order(
        self,
        client_id: int,
        pos_id: str,
        order_id: str,
        bonuses: int,
        is_paid: bool,
        discount_price: float | None,
    ) -> None:
        order = Order(
            pos_id=pos_id,
            starter_id=order_id,
            bonuses=bonuses,
            is_paid=is_paid,
            discount_price=discount_price,
            client_id=client_id,
        )
        self.session.add(order)

    def get_pos_ids_of_paid_orders(self, client_id: int) -> Sequence[str]:
        return self.session.scalars(select(Order.pos_id).where(Order.client_id == client_id, Order.is_paid)).all()

    def get_pos_ids_of_not_done_orders(self, client_id: int) -> Sequence[str]:
        return self.session.scalars(
            select(Order.pos_id).where(Order.client_id == client_id, Order.done.is_(False))
        ).all()

    def get_not_done_orders(self, client_id: int) -> Sequence[Order]:
        return self.session.scalars(select(Order).where(Order.client_id == client_id, Order.done.is_(False))).all()

    def set_order_to_done(self, client_id: int, order_pos_id: str) -> None:
        self.session.execute(
            update(Order).where(Order.client_id == client_id, Order.pos_id == order_pos_id).values(done=True)
        )

    def get_discount_price(self, client_id: int, pos_id: str) -> float:
        discount_price = self.session.scalar(
            select(Order.discount_price).where(Order.client_id == client_id, Order.pos_id == pos_id)
        )

        return discount_price or 0.0

    def get_orders_by_pos_ids(self, pos_ids: list[str]) -> Sequence[Order]:
        return self.session.scalars(select(Order).where(Order.pos_id.in_(pos_ids))).all()

    def get_order_by_client_and_starter_id(self, client_id: int, starter_id: str) -> Order | None:
        return self.session.scalar(select(Order).where(Order.client_id == client_id, Order.starter_id == starter_id))
