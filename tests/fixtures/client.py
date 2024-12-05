import pytest
from src.models import Client, Shop


@pytest.fixture
def create_client(db_session):
    def wrapper(
        client_id: str = "test_client_id",
        client_secret: str = "test_client_secret",
        is_active: bool = True,
        api_key: str = "test_client_api_key",
        currency_code: str = "123",
        discount_id: str = "",
        get_modifier_max_amount: bool = False,
        is_use_loyalty: bool = False,
        is_split_order_items_for_keeper: bool = False,
        is_use_modifier_external_id: bool = False,
        is_use_discounts_as_variable: bool = False,
        is_use_global_modifier_complex: bool = False,
        is_skip_update_order_payment_status: bool = False,
        is_use_minus_for_discount_amount: bool = False,
    ):
        client = Client(
            client_id=client_id,
            client_secret=client_secret,
            is_active=is_active,
            api_key=api_key,
            currency_code=currency_code,
            discount_id=discount_id,
            get_modifier_max_amount=get_modifier_max_amount,
            is_use_loyalty=is_use_loyalty,
            is_split_order_items_for_keeper=is_split_order_items_for_keeper,
            is_use_modifier_external_id=is_use_modifier_external_id,
            is_use_discounts_as_variable=is_use_discounts_as_variable,
            is_use_global_modifier_complex=is_use_global_modifier_complex,
            is_skip_update_order_payment_status=is_skip_update_order_payment_status,
            is_use_minus_for_discount_amount=is_use_minus_for_discount_amount,
        )
        db_session.add(client)
        db_session.commit()
        return client

    return wrapper


@pytest.fixture
def create_shop(db_session):
    def wrapper(
        client_id: int = 1,
        starter_id: int = 1,
        pos_id: str = "shop-1",
    ):
        shop = Shop(
            client_id=client_id,
            starter_id=starter_id,
            pos_id=pos_id,
        )

        db_session.add(shop)
        db_session.flush()

        return shop

    return wrapper
