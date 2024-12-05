from typing import Optional, Tuple, TypeVar, Any, Sequence

from httpx import HTTPError
from opentelemetry import trace
from starter_dto import pos
from starter_dto.pos.menu import ModifierInGroup, UpdateModifierOffer, CreateModifierOffer

from src.clients.pos_client import PosGatewayClient
from src.clients.rkeeper_client import RkeeperClient
from src.config import settings
from src.core.repositories.client import ClientRepository
from src.core.repositories.menu import MenuRepository
from src.core.repositories.order import OrderRepository
from src.core.repositories.schemas.client import MealOfferStarterCreated, MealStarterCreated
from sqlalchemy.orm import Session

from src.exceptions import ObjectDoesNotExist
from src.logger import get_logger
from src.models import Category, Shop, Meal, ModifierGroup, Client, Modifier, MealOffer, ModifierOffer
from src.schemas.rkeeper import (
    RKeeperCategory,
    RKeeperMeal,
    RKeeperMenu,
    RKeeperModifierGroups,
    RKeeperModifiers,
    RKeeperModifiersSchemes,
    RkeeperOrderStatusEnum,
    RkeeperPaymentStatusEnum,
    RkeeperPaymentTypeEnum,
    RKeeperShop,
    RKeeperLimitedListItem,
    RKeeperLimitedListItemTypeOfDish,
)
from src.tasks.schemas import DomainModifierSchema, DomainModifierGroupSchema
from src.utils.batch import generate_batch
from src.utils.enums import Entity

RkeeperTypes = TypeVar(
    "RkeeperTypes",
    list[RKeeperShop],
    list[RKeeperCategory],
    list[RKeeperModifierGroups],
    list[RKeeperModifiers],
    list[RKeeperMeal],
    list[DomainModifierSchema],
)

CreatedDataTypes = TypeVar(
    "CreatedDataTypes",
    list[pos.CreateShop],
    list[pos.CreateCategory],
    list[pos.CreateModifier],
)
UpdatedDataTypes = TypeVar(
    "UpdatedDataTypes",
    list[pos.UpdateShop],
    list[pos.UpdateCategory],
    list[pos.UpdateModifier],
)
SyncRkeeperTypes = TypeVar(
    "SyncRkeeperTypes",
    list[RKeeperShop],
    list[RKeeperCategory],
    list[DomainModifierSchema],
    list[RKeeperModifiers],
)

logger = get_logger("sync")
tracer = trace.get_tracer("rkeeper")


class MenuNotFound(Exception):
    pass


class Sync:
    def __init__(self, db: Session, client: Client, log: Any = None):
        self.db = db
        self.client = client
        self.pos_gateway = PosGatewayClient(client.api_key)
        self.rkeeper = RkeeperClient(client)
        self.client_repo = ClientRepository(db)
        self.menu_repo = MenuRepository(db)
        self.order_repo = OrderRepository(db)
        self.modifier_specific_external_id_map: dict[str, Modifier] = {}
        self.modifier_group_hashed_id_map: dict[str, ModifierGroup] = {}
        self.rkeeper_modifier_group_specific_hash_id_map: dict[str, str] = {}
        self.log = log or logger

    def shops(self) -> None:
        shops = self.client_repo.get_shops(self.client.id)
        rkeeper_shops = self.rkeeper.get_shops()

        self.log.debug("Sync shops", db=shops, rkeeper=rkeeper_shops)

        self._sync_shops(shops, rkeeper_shops)

    def menu(self, pos_shop_id: str) -> None:
        rkeeper_menu = self.rkeeper.get_menu(pos_shop_id)
        limited_list = self.rkeeper.get_limit_list()
        shop = self.client_repo.get_shop_by_pos_id(self.client.id, pos_shop_id)

        self._sync_categories(self.menu_repo.get_categories_by_client_id(self.client.id), rkeeper_menu.categories)
        self.db.flush()

        modifiers, modifier_groups = self._parse_modifiers_and_modifier_groups(rkeeper_menu)

        self.sync_modifiers(self.menu_repo.get_modifiers_by_project_id(self.client.project_id), modifiers)
        self.db.flush()

        self.sync_modifier_offers(
            self.menu_repo.get_modifier_offers_with_modifiers_by_shop_id(shop.id), modifiers, shop
        )
        self.db.flush()

        self.sync_modifier_groups(
            self.menu_repo.get_modifier_groups_by_project_id(self.client.project_id), modifier_groups
        )
        self.db.flush()

        self._sync_meals(self.menu_repo.get_meals_by_client_id(self.client.id), rkeeper_menu)
        self.db.flush()

        self._sync_meal_offers(self.menu_repo.get_meals_by_client_id(self.client.id), rkeeper_menu, shop, limited_list)
        self.db.flush()

    def sync_modifiers(self, db_modifiers: Sequence[Modifier], modifiers: dict[str, DomainModifierSchema]) -> None:
        new_modifiers, old_modifiers = self._split_modifiers_by_novelty(db_modifiers, list(modifiers.values()))

        self.modifier_specific_external_id_map.update(
            {modifier.specific_external_id: modifier for modifier in db_modifiers}
        )
        if old_modifiers:
            try:
                converted_data = [
                    pos.UpdateModifier(
                        id=self.modifier_specific_external_id_map[old_modifier.specific_external_id].starter_id,
                        **old_modifier.dict(),
                    )
                    for old_modifier in old_modifiers
                ]
                modifiers_to_update: list[Modifier] = []

                self.db.add_all(modifiers_to_update)

            except KeyError as e:
                self.log.error("Cannot find modifier to update", modifier_id=str(e))
                raise ObjectDoesNotExist(Entity.MODIFIER, str(e))

            self.pos_gateway.update_modifiers(converted_data)

        if new_modifiers:
            new_modifier_specific_external_id_map: dict[str, DomainModifierSchema] = {
                new_modifier.specific_external_id: new_modifier for new_modifier in new_modifiers
            }
            converted_data = [
                pos.CreateModifier(
                    pos_id=new_modifier.specific_external_id,
                    **new_modifier.dict(exclude={"pos_id"}),
                )
                for new_modifier in new_modifiers
            ]
            if created_objects := self.pos_gateway.create_modifiers(converted_data).data:
                domain_modifiers = []
                for out_object in created_objects:
                    new_modifier = new_modifier_specific_external_id_map[out_object.pos_id]
                    domain_modifiers.append(
                        Modifier(
                            pos_id=new_modifier.pos_id,
                            starter_id=out_object.id,
                            client_id=self.client.id,
                            external_id=new_modifier.external_id,
                            min_amount=new_modifier.min_amount,
                            max_amount=new_modifier.max_amount,
                        )
                    )
                self.db.add_all(domain_modifiers)

                self.modifier_specific_external_id_map.update(
                    {modifier.specific_external_id: modifier for modifier in domain_modifiers}
                )

    def sync_modifier_offers(
        self, db_modifier_offers: Sequence[ModifierOffer], modifiers: dict[str, DomainModifierSchema], shop: Shop
    ) -> None:
        new_modifier_offers, old_modifier_offers = self._split_by_novelty_by_pos_id(
            db_modifier_offers, list(modifiers.values())
        )

        modifier_offer_pos_starter_id = {offer.pos_id: offer.starter_id for offer in db_modifier_offers}

        if old_modifier_offers:
            try:
                converted_data = [
                    UpdateModifierOffer(
                        id=modifier_offer_pos_starter_id[modifier_offer.pos_id],
                        modifier_id=self.modifier_specific_external_id_map[
                            modifier_offer.specific_external_id
                        ].starter_id,
                        shop_id=shop.starter_id,
                        price=int(float(modifier_offer.price)),
                    )
                    for modifier_offer in old_modifier_offers
                ]
            except KeyError as e:
                self.log.error(
                    "Object does not exist.",
                    entity=Entity.MODIFIER,
                    pos_id=str(e),
                    modifier_specific_external_id_map=self.modifier_specific_external_id_map,
                    modifier_offer_pos_starter_id=modifier_offer_pos_starter_id,
                )
                raise ObjectDoesNotExist(Entity.MODIFIER, str(e))

            self.pos_gateway.update_modifier_offers(converted_data)

        if new_modifier_offers:
            modifier_offer_pos_id_map = {
                modifier_offer.pos_id: modifier_offer for modifier_offer in new_modifier_offers
            }
            try:
                converted_data = [
                    CreateModifierOffer(
                        modifier_id=self.modifier_specific_external_id_map[
                            modifier_offer.specific_external_id
                        ].starter_id,
                        pos_id=modifier_offer.pos_id,
                        shop_id=shop.starter_id,
                        price=int(float(modifier_offer.price)),
                    )
                    for modifier_offer in new_modifier_offers
                ]
            except KeyError as e:
                self.log.error(
                    "Object does not exist.",
                    entity=Entity.MODIFIER,
                    pos_id=str(e),
                    modifier_specific_external_id_map=self.modifier_specific_external_id_map,
                )
                raise ObjectDoesNotExist(Entity.MODIFIER, str(e))

            if created_objects := self.pos_gateway.create_modifier_offers(converted_data).data:
                domain_modifier_offers = []
                for starter_modifier_offer in created_objects:
                    new_modifier_offer = modifier_offer_pos_id_map[starter_modifier_offer.pos_id]
                    try:
                        domain_modifier_offers.append(
                            ModifierOffer(
                                modifier_id=self.modifier_specific_external_id_map[
                                    new_modifier_offer.specific_external_id
                                ].id,
                                shop_id=shop.id,
                                pos_id=new_modifier_offer.pos_id,
                                starter_id=starter_modifier_offer.id,
                            )
                        )
                    except KeyError as e:
                        self.log.error(
                            "Object does not exist.",
                            entity=Entity.MODIFIER,
                            pos_id=str(e),
                            modifier_pos_id_starter_id=self.modifier_specific_external_id_map,
                        )
                        raise ObjectDoesNotExist(Entity.MODIFIER, str(e))
                self.db.add_all(domain_modifier_offers)
                self.db.flush()

    def sync_modifier_groups(
        self, db_modifier_groups: Sequence[ModifierGroup], modifier_groups: dict[str, DomainModifierGroupSchema]
    ) -> None:
        self.rkeeper_modifier_group_specific_hash_id_map.update(
            {modifier_group.specific_id: modifier_group.hashed_id for modifier_group in modifier_groups.values()}
        )
        new_modifier_groups, old_modifier_groups = self._split_modifier_group_by_novelty(
            db_modifier_groups, list(modifier_groups.values())
        )

        if old_modifier_groups:
            self.modifier_group_hashed_id_map.update(
                {modifier_group.hashed_id: modifier_group for modifier_group in db_modifier_groups}
            )
            try:
                converted_data = []
                for modifier_group in old_modifier_groups:
                    db_modifier_group = self.modifier_group_hashed_id_map[modifier_group.hashed_id]
                    converted_data.append(
                        pos.UpdateModifierGroup(
                            id=db_modifier_group.starter_id,
                            modifiers=self._get_converted_modifiers(modifier_group.modifiers),
                            name=modifier_group.name,
                            max_amount=modifier_group.max_amount,
                            min_amount=modifier_group.min_amount,
                            required=modifier_group.required,
                        )
                    )

            except KeyError as e:
                self.log.error("Cannot find modifier group to update", modifier_group_id=str(e))
                raise ObjectDoesNotExist(Entity.MODIFIER_GROUP, str(e))

            self.pos_gateway.update_modifier_groups(converted_data)

        if new_modifier_groups:
            modifier_group_specific_id_map = {
                modifier_group.hashed_id: modifier_group for modifier_group in modifier_groups.values()
            }
            converted_data = [
                pos.CreateModifierGroup(
                    pos_id=new_modifier_group.hashed_id,
                    modifiers=self._get_converted_modifiers(new_modifier_group.modifiers),
                    name=new_modifier_group.name,
                    min_amount=new_modifier_group.min_amount,
                    max_amount=new_modifier_group.max_amount,
                    required=new_modifier_group.required,
                )
                for new_modifier_group in new_modifier_groups
            ]
            if created_objects := self.pos_gateway.create_modifier_groups(converted_data).data:
                domain_modifier_groups = []
                for starter_modifier_group in created_objects:
                    new_modifier_group = modifier_group_specific_id_map[starter_modifier_group.pos_id]
                    domain_modifier_groups.append(
                        ModifierGroup(
                            pos_id=new_modifier_group.pos_id,
                            starter_id=starter_modifier_group.id,
                            min_amount=new_modifier_group.min_amount,
                            max_amount=new_modifier_group.max_amount,
                            modifier_external_ids=new_modifier_group.modifier_external_ids,
                            client_id=self.client.id,
                        )
                    )
                self.db.add_all(domain_modifier_groups)
                self.db.flush()
                self.modifier_group_hashed_id_map.update(
                    {modifier_group.hashed_id: modifier_group for modifier_group in domain_modifier_groups}
                )

    def _sync_meals(self, meals_from_db: Sequence[Meal], rkeeper_menu: RKeeperMenu) -> None:
        for meal in rkeeper_menu.meals:
            meal.modifier_groups = self._find_modifier_groups(meal.scheme_id, rkeeper_menu.modifier_schemas)

        rkeeper_category_pos_ids = {category.pos_id for category in rkeeper_menu.categories}
        domain_categories = self.client_repo.get_category_by_client_id_and_pos_ids(
            self.client.id, rkeeper_category_pos_ids
        )
        category_pos_starter_id_map: dict[str, int] = {
            category.pos_id: category.starter_id for category in domain_categories
        }

        new_meals, old_meals = self._split_by_novelty_by_pos_id(meals_from_db, rkeeper_menu.meals)

        if old_meals:
            meal_pos_starter_id_map: dict[str, int] = {meal.pos_id: meal.starter_id for meal in meals_from_db}
            try:
                converted_data = [
                    meal.convert_to_pos_updater(
                        meal_pos_starter_id_map[meal.pos_id], category_pos_starter_id_map[meal.category_id]
                    )
                    for meal in old_meals
                ]
            except KeyError as e:
                self.log.error(
                    "Cannot find meal or meal_category to update",
                    meal_id=str(e),
                    meal_pos_starter_id_map=meal_pos_starter_id_map,
                    category_pos_starter_id_map=category_pos_starter_id_map,
                )
                raise ObjectDoesNotExist(Entity.MEAL, str(e))

            self.pos_gateway.update_meals(converted_data)

        if not new_meals:
            return

        try:
            new_meal_pos_id_map = {meal.pos_id: meal for meal in new_meals}
            converted_data = [
                pos.CreateMeal(
                    pos_id=meal.pos_id,
                    category_ids=[category_pos_starter_id_map[meal.category_id]] or [],
                    delivery_restrictions=[],
                    **meal.dict(exclude={"external_id", "pos_id"}),
                )
                for meal in new_meals
            ]
        except KeyError as e:
            self.log.error(
                "Cannot find meal_category to create meal",
                meal_category_id=str(e),
                category_pos_starter_id_map=category_pos_starter_id_map,
            )
            raise ObjectDoesNotExist(Entity.CATEGORY, str(e))

        if created_meals := self.pos_gateway.create_meals(converted_data).data:
            starter_created_meals = [
                MealStarterCreated(
                    external_id=new_meal_pos_id_map[meal.pos_id].external_id,
                    pos_id=new_meal_pos_id_map[meal.pos_id].pos_id,
                    id=meal.id,
                )
                for meal in created_meals
            ]
            self.menu_repo.create_meals(self.client.id, starter_created_meals)

    def _sync_meal_offers(
        self,
        meals_from_db: Sequence[Meal],
        rkeeper_menu: RKeeperMenu,
        shop: Shop,
        limited_list: list[RKeeperLimitedListItem],
    ) -> None:
        missing_meals: list[pos.menu.UpdateMealOffer] = self._get_local_meals_missing_on_rkeeper(
            meals_from_db, rkeeper_menu.meals, shop.id
        )

        if limited_list:
            limited_list_external_id_meal_map = {
                item.external_id: item
                for item in limited_list
                if item.restaurant_id == shop.pos_id and item.type_of_dish == RKeeperLimitedListItemTypeOfDish.PRODUCT
            }
            for meal in rkeeper_menu.meals:
                if limited_meal := limited_list_external_id_meal_map.get(meal.external_id):
                    meal.quantity = limited_meal.quantity

        db_meal_offers: list[MealOffer] = [
            offer for meal in meals_from_db for offer in meal.offers if offer.shop_id == shop.id
        ]

        new_meals, old_meals = self._split_by_novelty_by_pos_id(db_meal_offers, rkeeper_menu.meals)

        meal_pos_id_map: dict[str, Meal] = {meal.pos_id: meal for meal in meals_from_db}
        meal_offer_pos_starter_id = {
            offer.pos_id: offer.starter_id
            for meal in meals_from_db
            for offer in meal.offers
            if offer.shop_id == shop.id
        }
        meal_offer_update_data: list[pos.menu.UpdateMealOffer] = []
        if old_meals:
            try:
                meal_offer_update_data.extend(
                    meal.convert_to_meal_offer_updater(
                        meal_offer_pos_starter_id[meal.pos_id],
                        meal_pos_id_map[meal.pos_id].starter_id,
                        shop.pos_id,
                    )
                    for meal in old_meals
                )
            except KeyError as e:
                self.log.error(
                    "Object does not exist.",
                    entity=Entity.MEAL,
                    pos_id=str(e),
                    meal_pos_id_starter_id=meal_pos_id_map,
                    meal_offer_pos_starter_id=meal_offer_pos_starter_id,
                )
                raise ObjectDoesNotExist(Entity.MEAL, str(e))

        if missing_meals:
            meal_offer_update_data.extend(missing_meals)

        if meal_offer_update_data:
            for meal_offers_batch in generate_batch(meal_offer_update_data):
                self.pos_gateway.update_meal_offers(meal_offers_batch, shop.starter_id)

        if not new_meals:
            return

        try:
            meal_offer_create_data = [
                meal.convert_to_meal_offer_creator(
                    meal.pos_id,
                    meal_pos_id_map[meal.pos_id].starter_id,
                    shop.pos_id,
                )
                for meal in new_meals
            ]
        except KeyError as e:
            self.log.error("Object does not exist.", entity=Entity.MEAL, pos_id=e, map=meal_pos_id_map)
            raise ObjectDoesNotExist(Entity.MEAL, str(e))

        for meal_offer_batch in generate_batch(meal_offer_create_data):
            if created_meal_offers := self.pos_gateway.create_meal_offers(meal_offer_batch, shop.starter_id).data:
                domain_meal_offer_data = [
                    MealOfferStarterCreated(
                        meal_id=meal_pos_id_map[starter_meal_offer.pos_id].id, **starter_meal_offer.dict()
                    )
                    for starter_meal_offer in created_meal_offers
                ]
                self.menu_repo.create_meal_offers(domain_meal_offer_data, shop.id)

    @staticmethod
    def _split_modifiers_by_novelty(
        db_modifiers: Sequence[Modifier], modifiers: list[DomainModifierSchema]
    ) -> tuple[list[DomainModifierSchema], list[DomainModifierSchema]]:
        new_objects, old_objects = [], []
        if not modifiers:
            return [], []

        db_modifiers_ids = {db_object.specific_external_id: 1 for db_object in db_modifiers}
        for rkeeper_object in modifiers:
            object_exists = db_modifiers_ids.get(rkeeper_object.specific_external_id)
            old_objects.append(rkeeper_object) if object_exists else new_objects.append(rkeeper_object)

        return new_objects, old_objects

    def _get_converted_modifiers(self, modifiers: list[DomainModifierSchema]) -> list[ModifierInGroup]:
        converted_modifiers = []
        for modifier in sorted(modifiers, key=lambda el: el.specific_id):
            try:
                modifier_starter_id = self.modifier_specific_external_id_map[modifier.specific_external_id].starter_id
            except KeyError:
                self.log.error("Cannot find modifier to update", modifier_id=modifier.specific_external_id)
                raise ObjectDoesNotExist(Entity.MODIFIER, modifier.specific_external_id)

            converted_modifiers.append(
                ModifierInGroup(
                    id=modifier_starter_id,
                    min_amount=modifier.min_amount,
                    max_amount=modifier.max_amount,
                    required=modifier.required,
                )
            )
        return converted_modifiers

    def status_orders(self) -> None:
        rkeeper_status_of_orders = self.rkeeper.get_status_of_orders()
        not_done_orders = self.order_repo.get_not_done_orders(self.client.id)
        paid_orders = self.order_repo.get_pos_ids_of_paid_orders(self.client.id)
        not_done_order_pos_ids = set(order.pos_id for order in not_done_orders)
        rkeeper_orders = [order for order in rkeeper_status_of_orders if order.order_id in not_done_order_pos_ids]
        status_of_orders = []
        domain_order_pos_id_map = {
            order.pos_id: order
            for order in not_done_orders
            if order.pos_id in [rkeeper_order.order_id for rkeeper_order in rkeeper_orders]
        }

        logger.debug(
            "Rkeeper Orders",
            orders=rkeeper_orders,
            raw=rkeeper_status_of_orders,
            processed_orders=not_done_orders,
            domain_order_pos_id_map=domain_order_pos_id_map,
        )
        for status_order in rkeeper_orders:
            domain_orders = domain_order_pos_id_map[status_order.order_id]
            is_order_already_done = domain_orders.done
            with tracer.start_as_current_span("update order status") as span:
                span.set_attribute("rkeeper.order.id", str(status_order.order_id))
                span.set_attribute("order.id", str(status_order.order_external_id))
                span.set_attribute("rkeeper.order.status", str(status_order.order_status_id.name))
                span.set_attribute("client.id", self.client.client_id)

                logger.info("Order status", is_order_already_done=is_order_already_done, pos_id=status_order.order_id)
                if status_order.order_status_id in (RkeeperOrderStatusEnum.CANCELLED, RkeeperOrderStatusEnum.DELIVERED):
                    self.order_repo.set_order_to_done(self.client.id, status_order.order_id)
                    logger.info(
                        "Order status", is_order_already_done=is_order_already_done, pos_id=status_order.order_id
                    )

                span.set_attribute("rkeeper.order.payment_status", status_order.payment_status)
                can_pay = (
                    not self.client.is_skip_update_order_payment_status
                    and status_order.payment_type_id == RkeeperPaymentTypeEnum.ONLINE
                    and status_order.order_id in paid_orders
                    and status_order.order_external_id
                    and status_order.order_status_id in RkeeperOrderStatusEnum.ready_to_pay()
                    and status_order.payment_status == RkeeperPaymentStatusEnum.NOT_PAID
                )
                logger.info(
                    "Can we pay",
                    is_skip_update_order_payment_status=self.client.is_skip_update_order_payment_status,
                    pos_order_id=status_order.order_id,
                    paument_type=status_order.payment_type_id,
                    order_external_id=status_order.order_external_id,
                    status=status_order.order_status_id,
                    payment_status=status_order.payment_status,
                    paid_orders=paid_orders,
                    can_pay=can_pay,
                    client_id=self.client.client_id,
                )
                if can_pay:
                    discount_price = self.order_repo.get_discount_price(self.client.id, status_order.order_id)
                    logger.info(
                        "Data for pay api",
                        order_id=status_order.order_id,
                        full_amount=status_order.full_amount,
                        discount_price=discount_price,
                    )
                    try:
                        json = self.rkeeper.order_payment(status_order.order_id)
                    except HTTPError as e:
                        logger.error(
                            f"Payment error",
                            order_id=status_order.order_id,
                            client_id=self.client.client_id,
                            exc_info=str(e),
                        )
                        span.set_attribute("response.error", str(e))
                        continue

                    span.set_attribute("response", str(json))
                    if "errors" in json:
                        logger.warn(
                            f"Payment error for {status_order.order_id}, json={json}, client_id={self.client.client_id}"
                        )
                        span.set_attribute("response.error", str(json))
                else:
                    logger.info("Cant pay")

            if not is_order_already_done:
                starter_order_id = domain_orders.starter_id
                converted_data = status_order.convert_to_pos_updater(starter_order_id)

                if not converted_data:
                    continue

                status_of_orders.append(converted_data)

        if status_of_orders:
            self.pos_gateway.update_status_of_orders(status_of_orders)

    def _get_local_meals_missing_on_rkeeper(
        self, meals_from_db: Sequence[Meal], rkeeper_meals: list[RKeeperMeal], shop_id: int
    ) -> list:
        rkeeper_meal_ids = {meal.pos_id for meal in rkeeper_meals}

        meal_offer_pos_starter_id = {
            offer.pos_id: offer.starter_id
            for meal in meals_from_db
            for offer in meal.offers
            if offer.shop_id == shop_id
        }
        meal_offer_not_on_menu = []
        for domain_meal in meals_from_db:
            if domain_meal.pos_id not in rkeeper_meal_ids:
                try:
                    meal_offer_not_on_menu.append(
                        pos.menu.UpdateMealOffer(
                            quantity=0,
                            price=0,
                            meal_id=domain_meal.starter_id,
                            id=meal_offer_pos_starter_id[domain_meal.pos_id],
                        )
                    )
                except KeyError:
                    continue

        return meal_offer_not_on_menu

    def _sync_shops(self, shops_from_db: Sequence[Shop], rkeeper_shops: list[RKeeperShop]) -> None:
        new_objects, old_objects = self._split_by_novelty_by_pos_id(shops_from_db, rkeeper_shops)

        object_pos_starter_id_map: dict[str, int] = {obj.pos_id: obj.starter_id for obj in shops_from_db}
        if old_objects:
            try:
                converted_update_data = [
                    i.convert_to_pos_updater(object_pos_starter_id_map[i.pos_id]) for i in old_objects
                ]
            except KeyError as e:
                self.log.error("Cannot find object to update", object_id=str(e), enitity=Entity.SHOP)
                raise ObjectDoesNotExist(Entity.SHOP, str(e))

            self.pos_gateway.update_shops(converted_update_data)

        if not new_objects:
            return

        converted_create_data = [i.convert_to_pos_creator() for i in new_objects]
        if created_objects := self.pos_gateway.create_shops(converted_create_data).data:
            self.client_repo.create_shops(self.client.id, created_objects)

    def _sync_categories(
        self, categories_from_db: Sequence[Category], rkeeper_categories: list[RKeeperCategory]
    ) -> None:
        new_objects, old_objects = self._split_by_novelty_by_pos_id(categories_from_db, rkeeper_categories)
        object_pos_starter_id_map: dict[str, int] = {obj.pos_id: obj.starter_id for obj in categories_from_db}
        if old_objects:
            try:
                converted_update_data = [
                    i.convert_to_pos_updater(object_pos_starter_id_map[i.pos_id]) for i in old_objects
                ]
            except KeyError as e:
                self.log.error("Cannot find object to update", object_id=str(e), enitity=Entity.CATEGORY)
                raise ObjectDoesNotExist(Entity.CATEGORY, str(e))

            self.pos_gateway.update_categories(converted_update_data)

        if not new_objects:
            return

        converted_create_data = [i.convert_to_pos_creator() for i in new_objects]
        if created_objects := self.pos_gateway.create_categories(converted_create_data).data:
            self.menu_repo.create_categories(self.client.id, created_objects)

    def _find_modifier_groups(
        self,
        meal_scheme_id: Optional[str],
        modifier_schemas: list[RKeeperModifiersSchemes],
    ) -> list[int]:
        modifier_group_ids = []
        if meal_scheme_id:
            for modifier_schema in modifier_schemas:
                if modifier_schema.pos_id == meal_scheme_id:
                    for modifier_group in modifier_schema.modifier_groups:
                        try:
                            specific_modifier_group_id = (
                                f"{modifier_group.id}/{modifier_group.min_amount}/{modifier_group.max_amount}"
                            )
                            hashed_modifier_group_id = self.rkeeper_modifier_group_specific_hash_id_map[
                                specific_modifier_group_id
                            ]
                            modifier_group_starter_id = self.modifier_group_hashed_id_map[
                                hashed_modifier_group_id
                            ].starter_id

                            modifier_group_ids.append(modifier_group_starter_id)

                        except KeyError:
                            self.log.error(
                                "Cannot find modifier group to update",
                                modifier_group_id=modifier_group.id,
                                min_amount=modifier_group.min_amount,
                                max_amount=modifier_group.max_amount,
                                is_use_global_modifier_complex=self.client.is_use_global_modifier_complex,
                                rkeeper_modifier_group_specific_hash_id_map=self.rkeeper_modifier_group_specific_hash_id_map,
                                modifier_group_hashed_id_map=self.modifier_group_hashed_id_map,
                            )
                            raise ObjectDoesNotExist(Entity.MODIFIER_GROUP, modifier_group.id)

        return modifier_group_ids

    def _parse_modifiers_and_modifier_groups(
        self,
        rkeeper_menu: RKeeperMenu,
    ) -> Tuple[dict[str, DomainModifierSchema], dict[str, DomainModifierGroupSchema]]:
        modifier_data_by_id: dict[str, RKeeperModifiers] = {
            modifier.pos_id: modifier for modifier in rkeeper_menu.modifiers
        }
        modifier_group_by_id = {
            modifier_group.pos_id: modifier_group for modifier_group in rkeeper_menu.modifier_groups
        }
        modifiers_for_update = {}
        modifier_groups_for_update = {}
        for modifier_schema in rkeeper_menu.modifier_schemas:
            for modifier_group_in_schema in modifier_schema.modifier_groups:
                modifier_group = modifier_group_by_id[modifier_group_in_schema.id]
                modifiers_of_this_group = []

                # Нужно для формирования глобального id модификатора
                for modifier_id in modifier_group.modifiers:
                    modifier_data = modifier_data_by_id[modifier_id]

                    modifier_min_amount = 0
                    modifier_max_amount = modifier_group_in_schema.max_amount
                    if self.client.get_modifier_max_amount and modifier_data.max_amount:
                        modifier_max_amount = modifier_data.max_amount

                    modifier = DomainModifierSchema(
                        pos_id=modifier_id,
                        name=modifier_data.name,
                        price=modifier_data.price,
                        min_amount=modifier_min_amount,
                        max_amount=modifier_max_amount,
                        images=modifier_data.images,
                        required=True if modifier_min_amount else False,
                        external_id=modifier_data.external_id,
                    )
                    modifiers_for_update[modifier.specific_id] = modifier
                    modifiers_of_this_group.append(modifier)

                domain_modifier_group = DomainModifierGroupSchema(
                    pos_id=modifier_group_in_schema.id,
                    min_amount=modifier_group_in_schema.min_amount,
                    max_amount=modifier_group_in_schema.max_amount,
                    modifiers=modifiers_of_this_group,
                    name=modifier_group.name,
                    required=True if modifier_group_in_schema.min_amount else False,
                )

                # сохраняем группу
                if self.client.is_use_global_modifier_complex:
                    modifier_groups_for_update[domain_modifier_group.hashed_id] = domain_modifier_group
                else:
                    modifier_groups_for_update[domain_modifier_group.specific_id] = domain_modifier_group

        return modifiers_for_update, modifier_groups_for_update

    @staticmethod
    def _split_by_novelty_by_pos_id(
        data_from_db: Sequence[Category | Shop | Meal | MealOffer | ModifierGroup | Modifier | ModifierOffer],
        rkeeper_objects: RkeeperTypes,
    ) -> Tuple[RkeeperTypes, RkeeperTypes]:
        new_objects, old_objects = [], []
        if not rkeeper_objects:
            return [], []

        db_modifiers_ids = {db_object.pos_id: 1 for db_object in data_from_db}
        for rkeeper_object in rkeeper_objects:
            object_exists = db_modifiers_ids.get(rkeeper_object.pos_id)
            old_objects.append(rkeeper_object) if object_exists else new_objects.append(rkeeper_object)

        return new_objects, old_objects

    @staticmethod
    def _split_modifier_group_by_novelty(
        db_modifier_groups: Sequence[ModifierGroup],
        rkeeper_modifier_groups: list[DomainModifierGroupSchema],
    ) -> Tuple[list[DomainModifierGroupSchema], list[DomainModifierGroupSchema]]:
        new_groups, old_groups = [], []
        if not rkeeper_modifier_groups:
            return [], []

        db_modifier_groups_ids = {modifier_group.hashed_id: 1 for modifier_group in db_modifier_groups}
        for rkeeper_group in rkeeper_modifier_groups:
            object_exists = db_modifier_groups_ids.get(rkeeper_group.hashed_id)
            old_groups.append(rkeeper_group) if object_exists else new_groups.append(rkeeper_group)

        return new_groups, old_groups
