import datetime
from unittest.mock import patch

from starter_dto.enum import (
    DeliveryMethod,
    PaymentMethod,
    PaymentStatus,
    GatewayOrderStatus,
    OrderSource,
)
from starter_dto.pos.base import ObjectOut
from starter_dto.pos.order import OrderItem, ModifierInOrderItem, DeliveryProduct
from starter_dto.pos.settings import Address

from src.api.schemas import OrderWithCtx
from src.core.repositories.client import ClientRepository
from src.core.repositories.menu import MenuRepository
from src.core.repositories.schemas.client import MealStarterCreated
from src.models import Order, Shop
from src.schemas.rkeeper import (
    RKeeperOrder,
    RKeeperGuest,
    RKeeperOrderItems,
    OrderDraft,
    OrderDraftDiscounts,
    OrderDraftLoyaltyAmount,
)


@patch("src.clients.rkeeper_client.RkeeperClient.order_payment")
@patch("src.clients.rkeeper_client.RkeeperClient.create_order")
def test_create_order(
    mock_create_order,
    mock_order_payment,
    db_session,
    create_client,
    create_shop,
    create_modifier,
    create_meal,
    client,
    redis_client,
):
    domain_client = create_client(is_split_order_items_for_keeper=True)

    create_shop(domain_client.id, 1, "test_shop_pos_id")
    create_modifier(domain_client.id, 1, "test_modifier_id1")
    create_modifier(domain_client.id, 2, "test_modifier_id2")
    create_meal(domain_client.id, 1, "test_meals_id", "12345")
    create_meal(domain_client.id, 9999, "test_delivery_meal_id", "54321")

    mock_create_order.return_value = "test_pos_order_id"
    mock_order_payment.return_value = {"result": {}}
    modifiers = [
        ModifierInOrderItem(
            modifier_id=1,
            amount=2,
            price=49,
            title="Моцарелла",
            modifiers_group_id=1,
            modifiers_group_name="сыр",
        ),
        ModifierInOrderItem(
            modifier_id=2,
            amount=2,
            price=79,
            title="Пармезан",
            modifiers_group_id=1,
            modifiers_group_name="сыр",
        ),
    ]
    order_items = [
        OrderItem(
            order_item_id=1,
            discount_price=0,
            total_price=10,
            meal_id=1,
            quantity=2,
            price=10,
            modifiers=modifiers,
        ),
    ]

    create_data = OrderWithCtx(
        starter_id=1,
        global_id="111",
        order_items=order_items,
        bonuses=0,
        price=100,
        discount_price=0,
        delivery_price=10,
        total_price=110,
        address=Address(street="новокузнецкий", flat=1, floor=1, longitude=180, latitude=90),
        flatware_amount=0,
        delivery_type=DeliveryMethod.PICKUP,
        payment_type=PaymentMethod.CARD,
        payment_status=PaymentStatus.PAYED,
        delivery_datetime=datetime.datetime.now() + datetime.timedelta(days=1, hours=3),
        delivery_duration=50,
        delivery_product=DeliveryProduct(id=9999, price=300),
        submitted_datetime=datetime.datetime.now(),
        username="test",
        user_phone="11111111111",
        status=GatewayOrderStatus.CREATED,
        shop_id=1,
        source=OrderSource.web,
        ctx={"hz": "hz"},
    )
    url = "api/order"
    resp = client.post(url, data=create_data.json(), headers={"Authorization": domain_client.api_key})

    assert resp.json() == {"orderId": "test_pos_order_id"}
    db_order = db_session.query(Order).first()
    assert db_order.pos_id == "test_pos_order_id"
    assert db_order.starter_id == create_data.global_id
    assert db_order.bonuses == 0
    assert db_order.is_paid is True
    assert db_order.done is False
    assert db_order.discount_price == 0.0

    # check order item with quantity 2 is split by to items with quantity 1
    assert len(mock_create_order.call_args_list[0].args[0].order_items) == 3


@patch("src.clients.rkeeper_client.RkeeperClient.order_payment")
@patch("src.clients.rkeeper_client.RkeeperClient.create_order")
@patch("src.clients.rkeeper_client.RkeeperClient.preliminary_calculation")
def test_order_with_loyalty(
    mock_preliminary_calculation,
    mock_create_order,
    mock_order_payment,
    db_session,
    create_client,
    create_shop,
    create_meal,
    create_modifier,
    client,
    redis_client,
):
    domain_client = create_client(is_use_loyalty=True)

    create_shop(domain_client.id, 1, "test_shop_pos_id")
    create_modifier(domain_client.id, 1, "test_modifier_id1")
    create_modifier(domain_client.id, 2, "test_modifier_id2")
    create_meal(domain_client.id, 1, "test_meals_id")
    create_meal(domain_client.id, 9999, "test_delivery_meal_id")

    draft_order = OrderDraft(
        discounts=OrderDraftDiscounts(
            use_rk7_discounts=False,
            total=0,
            discount=0,
            discount_list=[],
        ),
        loyalty_amount=OrderDraftLoyaltyAmount(
            **{
                "totalAmount": 100.00,
                "loyaltyDiscountAmount": 0.0,
                "bonuses": {
                    "guestBalance": 100,
                    "rankName": "Базовый ранг",
                    "maxBonusesForPayment": 10,
                    "accrualWithPayment": 10,
                    "accrualWithoutPayment": 10,
                },
                "loyaltyPrograms": [],
                "fingerPrint": "fingerprint",
                "useRkLoyalty": True,
                "useLoyaltyBonusPayments": False,
                "loyaltyPromo": [],
                "loyaltyType": "rkLoyalty",
            }
        ),
    )
    mock_preliminary_calculation.return_value = draft_order
    mock_create_order.return_value = "test_pos_order_id"
    mock_order_payment.return_value = {"result": {}}
    modifiers = [
        ModifierInOrderItem(
            modifier_id=1,
            amount=2,
            price=49,
            title="Моцарелла",
            modifiers_group_id=1,
            modifiers_group_name="сыр",
        ),
        ModifierInOrderItem(
            modifier_id=2,
            amount=2,
            price=79,
            title="Пармезан",
            modifiers_group_id=1,
            modifiers_group_name="сыр",
        ),
    ]
    order_items = [
        OrderItem(
            order_item_id=1,
            discount_price=0,
            total_price=10,
            meal_id=1,
            quantity=1,
            price=10,
            modifiers=modifiers,
        ),
    ]

    create_data = OrderWithCtx(
        starter_id=1,
        global_id="111",
        order_items=order_items,
        bonuses=0,
        price=100,
        discount_price=0,
        delivery_price=10,
        total_price=110,
        address=Address(street="новокузнецкий", flat=1, floor=1, longitude=180, latitude=90),
        flatware_amount=0,
        delivery_type=DeliveryMethod.PICKUP,
        payment_type=PaymentMethod.CARD,
        payment_status=PaymentStatus.PAYED,
        delivery_datetime=datetime.datetime.now() + datetime.timedelta(days=1, hours=3),
        delivery_duration=50,
        delivery_product=DeliveryProduct(id=9999, price=300),
        submitted_datetime=datetime.datetime.now(),
        username="test",
        user_phone="11111111111",
        status=GatewayOrderStatus.CREATED,
        shop_id=1,
        source=OrderSource.web,
        ctx={"hz": "hz"},
    )
    url = "api/order"
    resp = client.post(url, data=create_data.json(), headers={"Authorization": domain_client.api_key})

    assert resp.json() == {"orderId": "test_pos_order_id"}

    db_order = db_session.query(Order).first()
    assert db_order.pos_id == "test_pos_order_id"
    assert db_order.starter_id == create_data.global_id
    assert db_order.bonuses == 0
    assert db_order.is_paid is True
    assert db_order.done is False
    assert db_order.discount_price == 0.0

    mock_create_order.call_once_with(
        RKeeperOrder(
            restaurant_id=1,
            guest=RKeeperGuest(username="test", user_phone="11111111111"),
            order_items=create_data.order_items
            + [
                RKeeperOrderItems(
                    id=9999,
                    meal_id=create_data.delivery_product.id,
                    quantity=1,
                    price=create_data.delivery_product.price,
                )
            ],
            loyalty_calculation=OrderDraftLoyaltyAmount(**draft_order.loyalty_amount.dict()),
            **create_data.dict(exclude={"discounts", "order_items"}),
        )
    )
    mock_preliminary_calculation.assert_called_once()
