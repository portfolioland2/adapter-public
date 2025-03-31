import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field, root_validator, validator
from starter_dto import pos
from starter_dto.enum import GatewayOrderStatus
from starter_dto.pos.menu import ModifierInGroup
from starter_dto.pos.settings import Address, CreateShop, DeliveryMethod, PaymentMethod, UpdateShop

from src.schemas.base import Base
from src.schemas.order import OrderStatusUpdater
from src.services.redis_client import Storage


class DeliveryTypeError(Exception):
    pass


class PaymentTypeError(Exception):
    pass


STREET_REGEXP = re.compile(
    r"((?:ул\.|улица|пер\.|переулок|аллея|бульвар|вал|взвод|въезд|дорога|заезд|кольцо|линия|луч|магистраль|"
    r"набережная|перспектива|пр-кт|площадь|проезд|проспект|проулок|разъезд|спуск|съезд|тракт|тупик|шоссе)"
    r"\s[\wА-Яа-я\-\ \.]+[^д|д\.|дом])[\.\,]?\s((?:д\.?|дом)?\s?[\d\/\\\-а-яa-z]+)$"
)

# TODO: N/A для Presto
# class SBISSettings(Base):
#     id: str
#     client_id: str = Field(
#         ...,
#         description="Выданный для [подключения по API](https://saby.ru/help/integration/api/auth)",
#     )
#     client_secret: str = Field(
#         ...,
#         description="Выданный для [подключения по API](https://saby.ru/help/integration/api/auth)",
#     )
#     currency_code: str | None = Field("", description="ID валюты оплаты")
#     discount_id: int | None = Field(None, description="Идентификатор скидки", alias="rkeeperDiscountId")
#     is_use_loyalty: bool
#     is_split_order_items_for_keeper: bool
#     is_use_modifier_external_id: bool
#     is_skip_update_order_payment_status: bool
#     project_name: str | None

# TODO: N/A для Presto
# class Project(Base):
#     project: str
#     data: RKeeperSettings
#     api_key: str

class WorkDays:
    def __init__(self, days_of_the_week: List[int]):
        self.days_of_the_week = days_of_the_week


class MainSchedule:
    def __init__(
        self,
        days_of_the_week: List[int],
        work_start_time: int,
        work_end_time: int,
        break_start_time: Optional[int] = None,
        break_end_time: Optional[int] = None,
    ):
        self.days_of_the_week = days_of_the_week
        self.work_start_time = work_start_time
        self.work_end_time = work_end_time
        self.break_start_time = break_start_time
        self.break_end_time = break_end_time


class ExceptionSchedule:
    def __init__(
        self,
        exception_interval_dates: List[int],
        work_start_time: int,
        work_end_time: int,
    ):
        self.exception_interval_dates = exception_interval_dates
        self.work_start_time = work_start_time
        self.work_end_time = work_end_time


class Schedule:
    def __init__(
        self,
        main_schedule: MainSchedule,
        exception_schedule: Optional[ExceptionSchedule] = None,
    ):
        self.main_schedule = main_schedule
        self.exception_schedule = exception_schedule


class WorkTime:
    def __init__(
        self,
        start: str,
        stop: str,
        workdays: WorkDays,
        schedule: Schedule,
    ):
        self.start = start
        self.stop = stop
        self.workdays = workdays
        self.schedule = schedule


class SalesPoint(Base):
    def __init__(
        self,
        address: str,
        default_price_list: Optional[int] = None,
        default_price_lists: Optional[List[int]] = None,
        product: str = "",
        id: int = Field(alias="pos_id"),
        image: Optional[str] = None,
        latitude: Optional[str] = None,
        locality: Optional[str] = None,
        longitude: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        phones: Optional[List[str]] = None,
        prices: Optional[List[int]] = None,
        worktime: Optional[WorkTime] = None,
    ):
        self.address = address
        self.default_price_list = default_price_list
        self.default_price_lists = default_price_lists or []
        self.product = product
        self.id = id
        self.image = image
        self.latitude = latitude
        self.locality = locality
        self.longitude = longitude
        self.name = name
        self.phone = phone
        self.phones = phones or []
        self.prices = prices or []
        self.worktime = worktime


class Outcome:
    def __init__(self, has_more: bool):
        self.has_more = has_more


class SBISShop(Base):
    def __init__(
        self,
        sales_points: List[SalesPoint],
        outcome: Optional[Outcome] = None,
    ):
        self.sales_points = sales_points
        self.outcome = outcome

    # actual_address: str | None
    # actual_address_lat: float | None
    # actual_address_lon: float | None
    # city: str | None
    # name: str
    # id: int
    # payment_types: list = [
    #     PaymentMethod.CARD,
    #     PaymentMethod.CASH,
    #     PaymentMethod.GOOGLE,
    #     PaymentMethod.APPLE,
    #     PaymentMethod.BONUS,
    #     PaymentMethod.CARD_TO_COURIER,
    #     PaymentMethod.CASH_TO_COURIER,
    # ]
    # delivery_types: list = [
    #     DeliveryMethod.COURIER,
    #     DeliveryMethod.INDOOR,
    #     DeliveryMethod.PICKUP,
    # ]

    class Config:
        fields = {"pos_id": "id"}

    @property
    def external_id(self) -> str:
        return self.id

    def convert_to_pos_creator(self) -> CreateShop:
        street_match = STREET_REGEXP.search(self.actual_address) if self.address else None
        address = Address(
            latitude=self.latitude,
            longitude=self.longitude,
            street=street_match["street"] if street_match else self.address,
            house=street_match["house"] if street_match else None,
            city=self.locality,
            comment=self.address,
        )

        return CreateShop(address=address, **self.dict())

    def convert_to_pos_updater(self, starter_id: int) -> UpdateShop:
        street_match = STREET_REGEXP.search(self.actual_address) if self.address else None
        address = Address(
            latitude=self.latitude,
            longitude=self.longitude,
            street=street_match["street"] if street_match else self.address,
            house=street_match["house"] if street_match else None,
            city=self.locality,
            comment=self.address,
        )

        return UpdateShop(id=starter_id, address=address, **self.dict())


class RKeeperCategory(Base):
    name: str
    pos_id: str

    class Config:
        fields = {"pos_id": "id"}

    @property
    def external_id(self) -> str:
        return self.pos_id

    def convert_to_pos_creator(self) -> pos.CreateCategory:
        return pos.CreateCategory(**self.dict())

    def convert_to_pos_updater(self, starter_id: int) -> pos.UpdateCategory:
        return pos.UpdateCategory(id=starter_id, **self.dict())


class RKeeperMeal(Base):
    name: str
    description: str | None
    external_id: str
    pos_id: str
    price: float
    scheme_id: str | None
    category_id: str
    proteins: int | None
    fats: int | None
    carbohydrates: int | None
    calories: int | None
    images: list[str]
    modifier_groups: list[int] | None
    is_contain_in_stop_list: list[str] | None
    quantity: float | None = None

    class Config:
        fields = {
            "pos_id": "id",
            "is_contain_in_stop_list": "isContainInStopList",
            "images": "imageUrls",
            "external_id": "externalId",
        }

    def convert_to_pos_creator(self, pos_id: str, category_starter_id: int) -> pos.CreateMeal:
        return pos.CreateMeal(
            pos_id=pos_id,
            category_ids=[category_starter_id] if category_starter_id else [],
            delivery_restrictions=[],
            **self.dict(exclude={"external_id", "pos_id"}),
        )

    def convert_to_pos_updater(self, starter_id: int, category_starter_id: int) -> pos.UpdateMeal:
        return pos.UpdateMeal(
            id=starter_id,
            category_ids=[category_starter_id] if category_starter_id else [],
            delivery_restrictions=[],
            **self.dict(),
        )

    def convert_to_meal_offer_creator(
        self, pos_id: str, meal_starter_id: int, pos_shop_id: str
    ) -> pos.menu.CreateMealOffer:
        is_in_stop_list = self.is_contain_in_stop_list and pos_shop_id in self.is_contain_in_stop_list
        return pos.menu.CreateMealOffer(
            quantity=0 if is_in_stop_list else self.quantity,
            price=self.price,
            meal_id=meal_starter_id,
            pos_id=pos_id,
        )

    def convert_to_meal_offer_updater(
        self, starter_id: int, meal_starter_id: int, pos_shop_id: str
    ) -> pos.menu.UpdateMealOffer:
        is_in_stop_list = self.is_contain_in_stop_list and pos_shop_id in self.is_contain_in_stop_list
        return pos.menu.UpdateMealOffer(
            quantity=0 if is_in_stop_list else self.quantity,
            price=self.price,
            meal_id=meal_starter_id,
            id=starter_id,
        )


class RKeeperModifiers(Base):
    pos_id: str
    external_id: str
    name: str
    price: str
    images: list
    max_amount: int | None

    class Config:
        fields = {"pos_id": "id", "images": "imageUrls", "max_amount": "maxCountForDish", "external_id": "externalId"}


class RKeeperModifierGroups(Base):
    pos_id: str
    name: str | None
    modifiers: list
    max_amount: int | None
    min_amount: int | None

    class Config:
        fields = {"pos_id": "id", "modifiers": "ingredients"}

    @property
    def external_id(self) -> str:
        return self.pos_id


class RKeeperCountOfUses(Base):
    id: str
    min_amount: int
    max_amount: int

    class Config:
        fields = {"min_amount": "minCount", "max_amount": "maxCount"}


class RKeeperModifiersSchemes(Base):
    pos_id: str
    modifier_groups: list[RKeeperCountOfUses]

    class Config:
        fields = {"modifier_groups": "ingredientsGroups", "pos_id": "id"}


class RKeeperMenu(Base):
    categories: list[RKeeperCategory]
    meals: list[RKeeperMeal]
    modifiers: list[RKeeperModifiers]
    modifier_groups: list[RKeeperModifierGroups]
    is_possible_delete: bool
    have_changes: bool | None
    modifier_schemas: list[RKeeperModifiersSchemes]

    class Config:
        fields = {
            "meals": "products",
            "modifiers": "ingredients",
            "modifier_groups": "ingredientsGroups",
            "modifier_schemas": "ingredientsSchemes",
            "is_possible_delete": "isPossibleDelete",
            "have_changes": "haveChanges",
        }

    @validator("categories", "meals", "modifiers", "modifier_groups", "modifier_schemas")
    def get_unique(cls, v: list) -> list:
        return list({item.pos_id: item for item in v}.values())


class RKeeperModifierInOrderItem(Base):
    id: str | None
    external_id: str | None
    modifier_id: int
    amount: int

    class Config:
        fields = {"amount": "quantity", "external_id": "externalId"}


class RKeeperOrderItems(Base):
    id: str | None
    external_id: str | None = None
    meal_id: int
    quantity: int
    price: int
    modifiers: list[RKeeperModifierInOrderItem] | None = None

    class Config:
        fields = {"modifiers": "ingredients"}


class RKeeperGuest(Base):
    username: str
    user_phone: str

    class Config:
        fields = {"user_phone": "phone", "username": "firstName"}


class RKeeperAddress(Base):
    street: str | None
    entrance: str | None
    comment: str | None
    latitude: str | None
    longitude: str | None
    floor: str | None
    flat: str | None
    full_address: str | None
    doorphone: str | None

    class Config:
        fields = {
            "latitude": "lat",
            "longitude": "lon",
            "flat": "apartmentNumber",
            "full_address": "fullAddress",
            "doorphone": "intercom",
        }

    @root_validator
    def computer_full_address(cls, values: dict) -> dict:
        values["full_address"] = f"{values.get('street')} {values.get('flat')} {values.get('entrance')}"

        return values


class RKeeperDeliveryType(str, Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class DiscountInList(Base):
    name: str
    amount: float
    is_manual: bool | None = Field(None, alias="isManual")
    is_variable: bool | None = Field(None, alias="isVariable")
    rkeeper_id: int = Field(..., alias="rk7Id")


class OrderDraftDiscounts(Base):
    use_rk7_discounts: bool = Field(..., alias="useRk7Discounts")
    total: float
    discount: float
    discount_list: list[DiscountInList]


class OrderDraftLoyaltyAmountBonuses(Base):
    guest_balance: float
    rank_name: str
    max_bonuses_for_payment: float
    accrual_with_payment: float
    accrual_without_payment: float


class DraftOrderLoyaltyProgram(Base):
    program_name: str
    program_notification: list[str]


class OrderDraftLoyaltyAmount(Base):
    total_amount: float
    loyalty_discount_amount: float
    bonuses: OrderDraftLoyaltyAmountBonuses | None
    loyalty_programs: list[DraftOrderLoyaltyProgram]
    finger_print: str
    use_rk_loyalty: bool
    use_loyalty_bonus_payments: bool
    loyalty_promo: list[Any]
    loyalty_type: str


class RKeeperOrder(Base):
    address: RKeeperAddress | None
    restaurant_id: str
    order_items: list[RKeeperOrderItems]
    delivery_type: str
    payment_type: str
    payment_status: str
    delivery_datetime: datetime | str | None
    guest: RKeeperGuest | None
    comment: str | None
    discounts: OrderDraftDiscounts | None
    manual_discounts: list | None
    flatware_amount: int
    soonest: bool = False
    use_loyalty: bool | None = False
    use_loyalty_bonus_payments: bool | None = False
    loyalty_calculation: OrderDraftLoyaltyAmount | None = None
    phone: str | None = None
    hide_loader: bool | None = True

    class Config:
        fields = {
            "delivery_type": "expeditionType",
            "payment_type": "paymentTypeId",
            "delivery_datetime": "expectedAt",
            "order_items": "dishList",
            "flatware_amount": "persons",
        }

    @validator("delivery_type")
    def computer_delivery_type(cls, value: str) -> str:
        if value == DeliveryMethod.COURIER:
            value = RKeeperDeliveryType.DELIVERY
        elif value in (DeliveryMethod.PICKUP, DeliveryMethod.INDOOR):
            value = RKeeperDeliveryType.PICKUP
        else:
            raise DeliveryTypeError

        return value

    @validator("payment_type")
    def compute_payment_type(cls, payment_method: PaymentMethod) -> Optional["RkeeperPaymentTypeEnum"]:
        if payment_method in (PaymentMethod.CARD, PaymentMethod.APPLE, PaymentMethod.GOOGLE):
            value = RkeeperPaymentTypeEnum.ONLINE
        elif payment_method in (PaymentMethod.CASH, PaymentMethod.CASH_TO_COURIER):
            value = RkeeperPaymentTypeEnum.CASH
        elif payment_method == PaymentMethod.CARD_TO_COURIER:
            value = RkeeperPaymentTypeEnum.CARD
        else:
            raise PaymentTypeError("Не получилось замаппить тип оплаты")

        return value


class RkeeperPaymentStatusEnum(str, Enum):
    NOT_PAID = "notPaid"
    PAID = "paid"


class RkeeperOrderStatusEnum(int, Enum):
    NEW = 1
    CREATED = 2
    CHECKED = 3
    KITCHEN = 4
    COOKING = 5
    COOKED = 6
    GETTING_ORDER = 7
    COLLECTED_ORDER = 8
    FROM_COURIER = 9
    EN_ROUTE = 10
    DONE = 11
    CANCELLED = 12
    DELIVERED = 13

    @classmethod
    def ready_to_pay(cls) -> list:
        return [
            cls.CHECKED,
            cls.KITCHEN,
            cls.COOKING,
            cls.COOKED,
            cls.GETTING_ORDER,
            cls.COLLECTED_ORDER,
            cls.FROM_COURIER,
            cls.EN_ROUTE,
        ]


statuses = {
    RkeeperOrderStatusEnum.NEW: GatewayOrderStatus.CREATED,
    RkeeperOrderStatusEnum.CREATED: GatewayOrderStatus.CHECKED,
    RkeeperOrderStatusEnum.CHECKED: GatewayOrderStatus.CHECKED,
    RkeeperOrderStatusEnum.KITCHEN: GatewayOrderStatus.IN_PROGRESS,
    RkeeperOrderStatusEnum.COOKING: GatewayOrderStatus.IN_PROGRESS,
    RkeeperOrderStatusEnum.COOKED: GatewayOrderStatus.COOKED,
    RkeeperOrderStatusEnum.GETTING_ORDER: GatewayOrderStatus.COOKED,
    RkeeperOrderStatusEnum.COLLECTED_ORDER: GatewayOrderStatus.COOKED,
    RkeeperOrderStatusEnum.FROM_COURIER: GatewayOrderStatus.ON_THE_WAY,
    RkeeperOrderStatusEnum.EN_ROUTE: GatewayOrderStatus.ON_THE_WAY,
    RkeeperOrderStatusEnum.DONE: GatewayOrderStatus.DONE,
    RkeeperOrderStatusEnum.DELIVERED: GatewayOrderStatus.DONE,
    RkeeperOrderStatusEnum.CANCELLED: GatewayOrderStatus.CANCELED,
}


class OrderDraft(Base):
    discounts: OrderDraftDiscounts
    loyalty_amount: OrderDraftLoyaltyAmount


class RkeeperPaymentTypeEnum(str, Enum):
    CASH = "cash"
    CARD = "card"
    ONLINE = "online"


class RKeeperOrderStatus(Base):
    order_id: str
    order_status_id: RkeeperOrderStatusEnum
    payment_type_id: RkeeperPaymentTypeEnum
    full_amount: float
    amount: float
    payment_status: str
    order_external_id: str | None
    discounts: OrderDraftDiscounts | None

    def convert_to_pos_updater(self, starter_order_id: str | None) -> Optional[OrderStatusUpdater]:
        # тестовые заказы не все созданы
        if not starter_order_id:
            return None

        status = statuses[self.order_status_id]
        if not status:
            status = GatewayOrderStatus.DRAFT

        return OrderStatusUpdater(id=starter_order_id, pos_number=self.order_id, status=status)


class RKeeperLimitedListItemTypeOfDish(str, Enum):
    PRODUCT = "product"


class RKeeperLimitedListItem(Base):
    restaurant_id: str
    type_of_dish: RKeeperLimitedListItemTypeOfDish | str
    external_id: str
    name: str
    quantity: float | None
