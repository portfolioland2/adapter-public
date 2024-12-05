from datetime import datetime
from typing import TypeAlias, Any

import pytz
from opentelemetry import trace
from starter_dto.enum import PaymentStatus, PaymentMethod

from src.api.order import OrderWithCtx
from src.clients.rkeeper_client import RkeeperClient
from src.core.repositories.client import ClientRepository
from sqlalchemy.orm import Session

from src.core.repositories.menu import MenuRepository
from src.core.repositories.order import OrderRepository
from src.exceptions import DiscountNotFound, ObjectDoesNotExist
from src.logger import get_logger
from src.models import Client
from src.repositories import DiscountRepository
from src.schemas.rkeeper import RKeeperGuest, RKeeperOrder, RKeeperOrderItems, DiscountInList, OrderDraftDiscounts
from src.utils.enums import Entity


RkeeperOrderId: TypeAlias = str


tracer = trace.get_tracer("order_service")


class OrderService:
    def __init__(self, db: Session, client: Client, log: Any):
        self.db = db
        self.log = log or get_logger("order_service")
        self.client = client
        self.client_repo = ClientRepository(self.db)
        self.menu_repo = MenuRepository(self.db)
        self.order_repo = OrderRepository(self.db)
        self.rkeeper_client = RkeeperClient(self.client)

    def create_order(self, starter_order: OrderWithCtx) -> RkeeperOrderId:
        restaurant_id = self.client_repo.get_shop_by_starter_id(self.client.id, starter_order.shop_id).pos_id
        self.log.info("Restaurant id", restaurant_id=restaurant_id)

        guest = RKeeperGuest(username=starter_order.username, user_phone=starter_order.user_phone)
        rkeeper_order = RKeeperOrder(
            restaurant_id=restaurant_id,
            guest=guest,
            **starter_order.dict(exclude={"discounts"}),
        )

        self.provide_discounts(starter_order, rkeeper_order)

        is_paid = (
            rkeeper_order.payment_status == PaymentStatus.PAYED and starter_order.payment_type != PaymentMethod.CASH
        )
        if is_paid and starter_order.payment_type not in (
            # в этих статусах комментарий не нужен, но заказ считается оплаченным.
            PaymentMethod.CARD_TO_COURIER,
            PaymentMethod.CASH_TO_COURIER,
        ):
            rkeeper_order.comment = f"ОПЛАЧЕН {rkeeper_order.comment if rkeeper_order.comment else ''}"

        self.process_items(starter_order, rkeeper_order)
        self.use_loyalty_and_split_order_items(starter_order, rkeeper_order)

        if starter_order.is_preorder and starter_order.delivery_datetime:
            delivery_datetime = starter_order.delivery_datetime
            if isinstance(delivery_datetime, str):
                delivery_datetime = datetime.strptime(delivery_datetime, "%Y-%m-%dT%H:%M:%SZ")
            rkeeper_order.delivery_datetime = delivery_datetime.astimezone(
                pytz.timezone(starter_order.timezone)
            ).isoformat()
        else:
            rkeeper_order.delivery_datetime = None
            rkeeper_order.soonest = True

        with tracer.start_as_current_span("order send") as send_span:
            send_span.set_attribute("rkeeper.order", rkeeper_order.json(by_alias=True))
            self.log.info(
                "Order for rkeeper",
                rkeeper_order=rkeeper_order.json(by_alias=True),
                client_id=self.client.client_id,
            )
            rkeeper_order_id = self.rkeeper_client.create_order(rkeeper_order)
            send_span.set_attribute("rkeeper.order.id", rkeeper_order_id)

        self.order_repo.create_order(
            self.client.id,
            rkeeper_order_id,
            starter_order.global_id,
            starter_order.bonuses,
            is_paid,
            starter_order.discount_price,
        )
        self.log.info(
            "Order created in RKeeper",
            pos_id=rkeeper_order_id,
            global_id=starter_order.global_id,
            rkeeper_order=rkeeper_order.json(by_alias=True),
        )

        return rkeeper_order_id

    def provide_discounts(self, starter_order: OrderWithCtx, rkeeper_order: RKeeperOrder) -> None:
        meal_discounts = sum([meal.discount_price for meal in starter_order.order_items])
        if starter_order.discount_price or meal_discounts or (starter_order.bonuses and not self.client.is_use_loyalty):
            try:
                db_discounts = DiscountRepository(self.db).get_discounts(self.client.id)
                domain_discount_starter_pos_id_map = {discount.starter_id: discount.pos_id for discount in db_discounts}
                finish_discount = (
                    starter_order.discount_price
                    - (0 if self.client.is_use_loyalty else starter_order.bonuses)
                    - meal_discounts
                )
                self.log.info("Finish discount", finish=finish_discount, meal=meal_discounts)
                discount_list = []
                if not db_discounts:
                    if finish_discount:
                        self.log.info("Has finish discount", finish=finish_discount)
                        discount_list = [
                            DiscountInList(
                                name="Стартер",
                                amount=(
                                    -finish_discount
                                    if not self.client.is_use_minus_for_discount_amount
                                    else finish_discount
                                ),
                                is_manual=False,
                                is_variable=True,
                                rkeeper_id=self.client.discount_id,
                            )
                        ]
                else:
                    is_manual = False if self.client.is_use_discounts_as_variable else True
                    for discount in starter_order.discounts:
                        pos_discount_id = domain_discount_starter_pos_id_map.get(discount.discount_id)
                        if not pos_discount_id:
                            self.log.error("Discount not found", discount_id=discount.discount_id)
                            raise DiscountNotFound(f"Не найдена скидка в адаптере Rkeeper: {discount.discount_id}")

                        discount_list.append(
                            DiscountInList(
                                name=discount.title,
                                amount=(
                                    discount.sum_with_cent
                                    if not self.client.is_use_minus_for_discount_amount
                                    else -discount.sum_with_cent
                                ),
                                is_manual=is_manual,
                                is_variable=not is_manual,
                                rkeeper_id=pos_discount_id,
                            )
                        )

                    if starter_order.bonuses + meal_discounts > 0:
                        discount_list.append(
                            DiscountInList(
                                name="Стартер",
                                amount=(
                                    starter_order.bonuses + meal_discounts
                                    if not self.client.is_use_minus_for_discount_amount
                                    else -starter_order.bonuses - meal_discounts
                                ),
                                is_manual=False,
                                is_variable=True,
                                rkeeper_id=self.client.discount_id,
                            )
                        )
                discounts = OrderDraftDiscounts(
                    discount_list=discount_list,
                    total=starter_order.total_price - starter_order.bonuses,
                    discount=finish_discount,
                    use_rk7_discounts=True,
                )
                rkeeper_order.discounts = discounts
            except TypeError as e:
                self.log.error("Project has not discounts", client_id=self.client.client_id)
                raise DiscountNotFound("Скидки не созданы") from e

    def process_items(self, starter_order: OrderWithCtx, rkeeper_order: RKeeperOrder) -> None:
        starter_meal_ids = [meal.meal_id for meal in starter_order.order_items]
        if starter_order.delivery_product and starter_order.delivery_product.id:
            starter_meal_ids.append(starter_order.delivery_product.id)

        meal_starter_id_map = {
            meal.starter_id: meal
            for meal in self.menu_repo.get_meals_by_client_id_and_starter_id(self.client.id, starter_meal_ids)
        }

        if starter_order.delivery_product and (
            delivery_product := meal_starter_id_map.get(starter_order.delivery_product.id)
        ):
            rkeeper_order_item = RKeeperOrderItems(
                id=delivery_product.pos_id,
                meal_id=starter_order.delivery_product.id,
                quantity=1,
                price=starter_order.delivery_product.price,
            )
            if self.client.is_use_meal_external_id and delivery_product.external_id:
                rkeeper_order_item.id = None
                rkeeper_order_item.external_id = delivery_product.external_id

            rkeeper_order.order_items.append(rkeeper_order_item)

        modifier_starter_ids = {
            modifier.modifier_id for order_item in starter_order.order_items for modifier in order_item.modifiers
        }

        domain_modifiers = self.menu_repo.get_project_modifier_by_starter_ids(
            self.client.project_id, modifier_starter_ids
        )
        modifier_starter_pos_id_map = {modifier.starter_id: modifier.external_id for modifier in domain_modifiers}

        if rkeeper_order.order_items:
            for order_item in rkeeper_order.order_items:
                domain_order_item = meal_starter_id_map.get(order_item.meal_id)
                if not (domain_order_item and (domain_order_item.pos_id or domain_order_item.external_id)):
                    raise ObjectDoesNotExist(Entity.MEAL, str(order_item.meal_id))

                if self.client.is_use_meal_external_id and domain_order_item.external_id:
                    order_item.id = None
                    order_item.external_id = domain_order_item.external_id
                else:
                    order_item.id = domain_order_item.pos_id

                if not order_item.modifiers:
                    continue

                for ingredient in order_item.modifiers:
                    modifier_pos_id = modifier_starter_pos_id_map.get(ingredient.modifier_id)
                    if not modifier_pos_id:
                        raise ObjectDoesNotExist(Entity.MODIFIER, str(ingredient.modifier_id))

                    ingredient.external_id = modifier_pos_id

    def use_loyalty_and_split_order_items(self, starter_order: OrderWithCtx, rkeeper_order: RKeeperOrder) -> None:
        # метод предварительного расчета вызываем, чтоб получить discounts
        if self.client.is_use_loyalty:
            rkeeper_order.use_loyalty = True
            rkeeper_order.use_loyalty_bonus_payments = True if starter_order.bonuses else False
            rkeeper_order.phone = "+" + starter_order.user_phone
            order_draft = self.rkeeper_client.preliminary_calculation(rkeeper_order)
            rkeeper_order.loyalty_calculation = order_draft.loyalty_amount

        # beanhearts просит, чтобы несколько одинаковых блюл шли разными объектами с кол-вом 1,
        # а не 1 объектов с кол-вом 1+
        if self.client.is_split_order_items_for_keeper:
            clean_items = []
            for item in rkeeper_order.order_items:
                if item.quantity == 1:
                    clean_items.append(item)
                    continue

                item_quantity = item.quantity
                for _ in range(item_quantity):
                    item.quantity = 1
                    clean_items.append(item)

            rkeeper_order.order_items = clean_items
