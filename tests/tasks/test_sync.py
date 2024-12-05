from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from starter_dto.pos import ObjectOutList
from starter_dto.pos.base import ObjectOut
from starter_dto.pos.menu import CreateMealOffer

from src.clients.pos_client import PosGatewayClient
from src.config import settings
from src.core.repositories.client import ClientRepository
from src.core.repositories.menu import MenuRepository
from src.core.repositories.schemas.client import MealStarterCreated, MealOfferStarterCreated
from src.models import Shop, Modifier, ModifierOffer
from src.schemas.rkeeper import (
    RKeeperShop,
    RKeeperMenu,
    RKeeperCategory,
    RKeeperLimitedListItem,
)
from src.tasks.sync import Sync


@patch("src.clients.rkeeper_client.RkeeperClient.get_shops")
@patch("src.clients.pos_client.PosGatewayClient.create_shops")
def test_sync_shops(mock_create_shops, mock_get_shops, db_session, create_client, redis_client):
    domain_client = create_client()
    client_repo = ClientRepository(db_session)
    mock_get_shops.return_value = [
        RKeeperShop(
            **{
                "name": "test1",
                "pos_id": "11111",
                "payment_type": ["cash", "card"],
                "delivery_types": ["courier", "pickup"],
                "actual_address_lat": 44.4,
                "actual_address_lon": 22.2,
                "actual_address": "Москва Невский проспект 123",
            }
        ),
        RKeeperShop(
            **{
                "name": "test2",
                "pos_id": "22222",
                "payment_type": ["cash", "card"],
                "delivery_types": ["courier", "pickup"],
                "actual_address_lat": 44.4,
                "actual_address_lon": 22.2,
                "actual_address": "Москва Невский проспект 123",
            }
        ),
    ]
    mock_create_shops.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "11111", "id": 1}),
            ObjectOut(**{"posId": "22222", "id": 2}),
        ],
        count=0,
    )

    Sync(db_session, domain_client).shops()
    db_session.commit()
    shops = client_repo.get_shops(domain_client.id)
    shop_starter_id_object_map: dict[int, Shop] = {shop.starter_id: shop for shop in shops}
    assert len(shops) == 2
    for pos_id, starter_id in {"11111": 1, "22222": 2}.items():
        shop = shop_starter_id_object_map[starter_id]
        assert shop.pos_id == pos_id


def test_split_by_novelty(db_session, create_client, create_shop, redis_client):
    domain_client = create_client()
    create_shop(domain_client.id, 2222, "11111")
    create_shop(domain_client.id, 4444, "33333")

    new_data = [
        RKeeperShop(
            **{
                "name": "test1",
                "pos_id": "11111",
                "payment_type": ["cash", "card"],
                "delivery_types": ["courier", "pickup"],
            }
        ),
        RKeeperShop(
            **{
                "name": "test2",
                "pos_id": "66666",
                "payment_type": ["cash", "card"],
                "delivery_types": ["courier", "pickup"],
            }
        ),
    ]
    sync = Sync(db_session, domain_client)
    new_shops, old_shops = sync._split_by_novelty_by_pos_id(
        ClientRepository(db_session).get_shops(domain_client.id), new_data
    )

    for new_shop in new_shops:
        assert new_shop.pos_id == "66666"

    for old_shop in old_shops:
        assert old_shop.pos_id == "11111"


@patch("src.clients.rkeeper_client.RkeeperClient.get_menu")
@patch("src.clients.pos_client.PosGatewayClient.create_categories")
@patch("src.clients.pos_client.PosGatewayClient.create_meal_offers")
@patch("src.clients.pos_client.PosGatewayClient.create_meals")
@patch("src.clients.pos_client.PosGatewayClient.create_modifiers")
@patch("src.clients.pos_client.PosGatewayClient.create_modifier_offers")
@patch("src.clients.pos_client.PosGatewayClient.create_modifier_groups")
@patch("src.clients.rkeeper_client.RkeeperClient.get_limit_list")
def test_sync_menu(
    get_limit_list,
    mock_modifier_groups,
    mock_modifier_offers,
    mock_modifiers,
    mock_meals,
    mock_meal_offers,
    mock_categories,
    mock_menu,
    db_session,
    create_client,
    create_shop,
    create_meal,
    create_modifier,
    create_modifier_offer,
    redis_client,
    rkeeper_menu,
):
    domain_client = create_client()
    pos_shop_id = "123"
    shop = create_shop(domain_client.id, 1, pos_shop_id)

    modifier = create_modifier(client_id=domain_client.id, starter_id="8888", external_id="8888", pos_id="8888")
    create_modifier_offer(shop_id=shop.id, starter_id="888", modifier_id=modifier.id)

    mock_menu.return_value = RKeeperMenu(**rkeeper_menu)
    get_limit_list.return_value = [
        RKeeperLimitedListItem(
            restaurant_id="123",
            type_of_dish="product",
            external_id="1111",
            name="ProductName",
            quantity=0.0,
        )
    ]
    mock_categories.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "55555", "id": 11}),
        ],
        count=0,
    )

    mock_meals.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "prodictId", "id": 111}),
        ],
        count=0,
    )

    mock_meal_offers.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "prodictId", "id": 1}),
        ],
        count=0,
    )
    mock_modifier_groups.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "cdeacd338b1768160db8a733e7ebb1dd", "id": 1111}),
        ],
        count=0,
    )
    mock_modifier_offers.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "2222", "id": 1001}),
        ],
        count=0,
    )
    mock_modifiers.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "2222/0/1", "id": 11111}),
        ],
        count=0,
    )
    Sync(db_session, domain_client).menu(pos_shop_id)
    db_session.commit()

    menu_repo = MenuRepository(db_session)
    categories = menu_repo.get_categories_by_client_id(domain_client.id)
    meals = menu_repo.get_meals_by_client_id(domain_client.id)
    modifier_groups = menu_repo.get_modifier_groups_by_client_id(domain_client.id)
    modifiers = menu_repo.get_modifiers_by_client_id(domain_client.id)
    modifier_offers = db_session.query(ModifierOffer).all()

    mock_meal_offers.assert_called_once_with(
        [CreateMealOffer(quantity=0, price=500.0, in_menu=True, meal_id=111, pos_id="prodictId")], 1
    )

    assert len(categories) == 1
    assert categories[0].pos_id == "55555"
    assert categories[0].starter_id == 11

    assert len(meals) == 1
    assert meals[0].pos_id == "prodictId"
    assert meals[0].starter_id == 111

    assert len(modifier_groups) == 1
    assert modifier_groups[0].pos_id == "IngredientGroupId"
    assert modifier_groups[0].min_amount == 0
    assert modifier_groups[0].max_amount == 1
    assert modifier_groups[0].starter_id == 1111

    assert len(modifiers) == 2
    assert modifiers[1].pos_id == "2222"
    assert modifiers[1].min_amount == 0
    assert modifiers[1].max_amount == 1
    assert modifiers[1].starter_id == 11111

    assert len(modifier_offers) == 2
    assert modifier_offers[1].modifier_id == modifiers[1].id
    assert modifier_offers[1].pos_id == "2222"
    assert modifier_offers[1].starter_id == 1001

    meal_offers = next(
        (shop for shop in ClientRepository(db_session).get_shops(domain_client.id) if shop.pos_id == pos_shop_id)
    ).meal_offers
    assert len(meal_offers) == 1
    assert meal_offers[0].pos_id == "prodictId"
    assert meal_offers[0].starter_id == 1


@patch("src.clients.pos_client.PosGatewayClient.create_categories")
def test_sync_categories(mock_create_categories, db_session, create_client, redis_client):
    menu_repo = MenuRepository(db_session)
    domain_client = create_client()
    categories = menu_repo.get_categories_by_client_id(domain_client.id)

    rkeeper_categories = [
        RKeeperCategory(**{"pos_id": "test_pos_id", "name": "test"}),
        RKeeperCategory(**{"pos_id": "test_pos_id2", "name": "test2"}),
    ]

    mock_create_categories.return_value = ObjectOutList(
        data=[
            ObjectOut(**{"posId": "test_pos_id", "id": 1}),
            ObjectOut(**{"posId": "test_pos_id2", "id": 2}),
        ],
        count=0,
    )

    sync = Sync(db_session, domain_client)

    sync._sync_categories(
        categories,
        rkeeper_categories,
    )
    db_session.commit()

    categories = menu_repo.get_categories_by_client_id(domain_client.id)
    assert len(categories) == 2
    category_pos_id_map = {category.pos_id: category for category in categories}
    for pos_id, starter_id in {"test_pos_id": 1, "test_pos_id2": 2}.items():
        category = category_pos_id_map[pos_id]
        assert category.starter_id == starter_id


def test_get_local_meals_missing_on_rkeeper(db_session, create_client, create_shop, create_meal, rkeeper_menu):
    domain_client = create_client()
    menu_repo = MenuRepository(db_session)

    shop = create_shop(domain_client.id, 2222, "11111")
    create_shop(domain_client.id, 4444, "33333")

    create_meal(domain_client.id, 111, "123")
    create_meal(domain_client.id, 222, "234")
    create_meal(domain_client.id, 444, "prodictId")
    db_meals = menu_repo.get_meals_by_client_id(domain_client.id)

    meal_offers_to_create = []
    meal_offer_starter_id = 1
    for meal in db_meals:
        meal_offers_to_create.append(
            MealOfferStarterCreated(
                id=meal_offer_starter_id,
                pos_id=meal.pos_id,
                meal_id=meal.id,
            )
        )
        meal_offer_starter_id += 1

    menu_repo.create_meal_offers(meal_offers_to_create, shop.id)
    db_session.commit()

    rkeeper_menu = RKeeperMenu(**rkeeper_menu)
    sync = Sync(db_session, domain_client)

    db_meals = menu_repo.get_meals_by_client_id(domain_client.id)
    missing_meals = sync._get_local_meals_missing_on_rkeeper(db_meals, rkeeper_menu.meals, shop.id)

    missing_meals_ids = [meal.id for meal in missing_meals]
    assert missing_meals_ids == [1, 2]
