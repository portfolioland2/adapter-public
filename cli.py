import click
from redis import Redis

from src.config import settings
from src.core.repositories.client import ClientRepository
from src.db import SessionLocal
from src.repositories import DiscountRepository
from src.models import Client, Project, Order, Discount, Category, Modifier, ModifierGroup, Meal, Shop, MealOffer
from src.services.redis_client import Storage
from src.clients.pos_client import PosGatewayClient
from src.tasks.tasks import sync_menu, transfer_client_menu_to_project


def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


@click.group()
def cli():
    pass


@cli.command()
@click.option("--client-id")
@click.option("--client-secret")
@click.option("--api-key")
@click.option("--currency-code")
def add_client(client_id: str, client_secret: str, api_key: str, currency_code: str) -> None:
    """
    Create a client
    """
    client = Client(
        client_id=client_id,
        client_secret=client_secret,
        api_key=api_key,
        currency_code=currency_code,
    )
    Storage().create_client(client)
    PosGatewayClient(api_key).register_webhook()


@cli.command()
def get_clients() -> None:
    """
    Get a client
    """
    clients = Storage().get_active_clients()
    click.echo(clients)


@cli.command()
@click.option("--api-key")
def initialization_in_pos_gateway(api_key: str):
    PosGatewayClient(api_key).register_webhook_for_settings()


@cli.command()
@click.option("--client-id")
@click.option(
    "--yes",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Вы уверены что хотите удалить клиента?",
)
def delete_client(client_id: str):
    Storage().delete_client(client_id)


@cli.command()
@click.option("--client-id")
@click.option("--currency-code")
def set_currency_code(client_id: str, currency_code: str):
    Storage().set_currency_code(client_id, currency_code)


@cli.command()
@click.option("--client-id")
@click.option("--client-secret")
def set_client_secret(client_id: str, client_secret: str):
    Storage().set_client_secret(client_id, client_secret)


@cli.command("use-loyalty")
@click.option("--client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_is_use_loyalty(client_id: str, on: bool | None = None, off: bool | None = None):
    if on and off:
        click.echo("Либо on либо off")
        return
    value = True if on else False
    Storage().set_is_use_loyalty(client_id, value)


@cli.command("split-order-items")
@click.option("--client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_is_split_order_items_for_keeper(client_id: str, on: bool, off: bool):
    if on and off:
        click.echo("Либо on либо off")
        return
    value = True if on else False
    Storage().set_is_split_order_items_for_keeper(client_id, value)


@cli.command("set-complicated-modifier-id")
@click.option("--client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_complicated_modifier_id(client_id: str, on: bool, off: bool):
    if on and off:
        click.echo("Либо on либо off")
        return
    value = True if on else False
    Storage().set_complicated_modifier_id(client_id, value)


@cli.command()
@click.option("--client-id")
def set_get_modifier_max_amount(client_id: str):
    Storage().set_modifier_max_amount(client_id)


@cli.command()
@click.option("--login")
@click.option("--starter-id")
@click.option("--pos-id")
def create_discount(login: str, starter_id: str, pos_id: int):
    discount_repo = DiscountRepository()
    discount_repo.create_discount(login, pos_id, starter_id)


@cli.command()
@click.option("--client-id")
@click.option("--discount-id")
def set_discount_id(client_id: str, discount_id: str):
    Storage().set_discount_id(client_id, int(discount_id))


@cli.command()
@click.option("--client-id")
def clear_discount(client_id: str) -> None:
    discount_repo = DiscountRepository()
    discount_repo.clear_discounts(client_id)


@cli.command()
@click.option("--client-id")
@click.option(
    "--yes",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Вы уверены что хотите почистить меню клиента?",
)
def clear_menu(client_id: str) -> None:
    Storage().clear_menu(client_id)


@cli.command()
@click.option("--client-id")
@click.option(
    "--yes",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Вы уверены что хотите почистить шопы клиента?",
)
def clear_shops(client_id: str) -> None:
    Storage().clear_shops(client_id)


@cli.command()
@click.option("--client-id")
def sync_client_menu(client_id: str) -> None:
    sync_menu.s(client_id)


@cli.command()
def show_currency_codes():
    clients = Storage().get_active_clients()
    for client in clients:
        click.echo(f"{client.client_id} - {client.currency_code} - {client.discount_id}")


@cli.command()
@click.option("--client-id")
@click.option(
    "--yes",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Вы уверены что хотите удалить клиент?",
)
def remove_client(client_id: str) -> None:
    Storage().remove_client(client_id)


@cli.command()
@click.option("--global-id")
def ignore_order(order_id: str) -> None:
    Storage().set_order_cache(order_id, ex=3600 * 24)


@cli.command()
@click.option("--client-id")
@click.option("--pos-id")
@click.option("--starter-id")
def set_shop_id(client_id, pos_id, starter_id):
    Storage().set_shop_id(client_id, pos_id, int(starter_id))


@cli.command()
@click.option("--client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_is_use_modifier_external_id(client_id: str, on: bool | None = None, off: bool | None = None):
    if on and off:
        click.echo("Либо on либо off")
        return
    value = on is True
    Storage().set_is_use_modifier_external_id(client_id, value)


@cli.command()
@click.option("--client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_is_use_discounts_as_variable(client_id: str, on: bool | None = None, off: bool | None = None):
    if on and off:
        click.echo("Либо on либо off")
        return
    value = on is True
    Storage().set_is_use_discounts_as_variable(client_id, value)


@cli.command()
@click.option("--client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_is_skip_update_order_payment_status(client_id: str, on: bool | None = None, off: bool | None = None):
    if on and off:
        click.echo("Либо on либо off")
        return
    value = on is True
    Storage().set_is_skip_update_order_payment_status(client_id, value)


@cli.command()
@click.argument("client-id")
@click.argument("project_name")
def set_project_name(client_id: str, project_name: str) -> None:
    Storage().set_project_name(client_id, project_name)


@cli.command()
def create_test() -> None:
    s = Storage()
    external_ids = s.get_modifier_external_ids("beanhearts")
    ids = {3: "4"}
    result = ids | external_ids
    s.save_modifiers_external_id_map("beanhearts", result)


@cli.command()
@click.argument("client-id")
@click.option("--on", is_flag=True, default=False)
@click.option("--off", is_flag=True, default=False)
def set_client_active(client_id: str, on: bool, off: bool) -> None:
    if on and off:
        click.echo("Либо on либо off")
        return
    value = True if on else False
    Storage().set_active_client(client_id, value)


@cli.command(name="migrate")
def migrate_from_redis_to_postgres() -> None:
    redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    print("Start migrate")
    with SessionLocal() as session:
        client_repo = ClientRepository(session)

        clients = redis.json().get("clients")
        project_by_title_map: dict[str, Project] = {}
        for client_id, client_data in clients.items():
            print("Migrate", client_id)
            client = Client(
                client_id=client_id,
                client_secret=client_data.get("client_secret"),
                is_active=client_data.get("is_active", False),
                api_key=client_data.get("api_key"),
                currency_code=client_data.get("currency_code", settings.RUBLE_CURRENCY_CODE),
                discount_id=client_data.get("discount_id"),
                get_modifier_max_amount=client_data.get("get_modifier_max_amount", False),
                is_use_loyalty=client_data.get("is_use_loyalty", False),
                is_split_order_items_for_keeper=client_data.get("is_split_order_items_for_keeper", False),
                is_use_modifier_external_id=client_data.get("is_use_modifier_external_id", False),
                is_use_discounts_as_variable=client_data.get("is_use_discounts_as_variable", False),
                is_use_global_modifier_complex=client_data.get("is_use_global_modifier_complex", False),
                is_skip_update_order_payment_status=client_data.get("is_skip_update_order_payment_status", False),
                is_use_minus_for_discount_amount=client_data.get("is_use_minus_for_discount_amount", False),
            )

            if project_title := client_data.get("project_name"):
                project, _ = project_by_title_map.get(project_title) or client_repo.get_or_create_project(project_title)
                client.project_id = project.id

            session.add(client)
            session.flush()

            client_objects = client_data.get("objects", {})
            client_shops = client_objects.get("shops", {})
            client_menu = client_objects.get("menu", {})
            client_orders = client_objects.get("orders", {})
            client_discounts = client_objects.get("discounts", {})

            project_data = redis.json().get(project_title) if project_title else {}

            shop_pos_domain_id_map: dict[str, int] = {}
            if client_shops:
                shops = [
                    Shop(client_id=client.id, starter_id=shop_starter_id, pos_id=shop_pos_id)
                    for shop_pos_id, shop_starter_id in client_shops.items()
                ]
                session.add_all(shops)
                session.flush()
                shop_pos_domain_id_map.update({shop.pos_id: shop.id for shop in shops})

            if client_orders:
                orders = [
                    Order(
                        client_id=client.id,
                        pos_id=order_id,
                        starter_id=order_data["id"],
                        bonuses=order_data["bonuses"],
                        is_paid=order_data["is_paid"],
                        done=order_data["done"],
                        discount_price=order_data["discount_price"],
                    )
                    for order_id, order_data in client_orders.items()
                ]
                session.add_all(orders)

            if client_discounts:
                discounts = [
                    Discount(
                        client_id=client.id,
                        starter_id=starter_id,
                        pos_id=pos_id,
                    )
                    for starter_id, pos_id in client_discounts.items()
                ]
                session.add_all(discounts)

            if client_menu:
                categories = [
                    Category(pos_id=pos_id, starter_id=starter_id, client_id=client.id)
                    for pos_id, starter_id in client_menu.get("categories", {}).items()
                ]
                modifier_starter_external_id_map = project_data.get("modifiers_external_ids", {})
                modifiers = [
                    Modifier(
                        pos_id=pos_id.split("/")[0] if "/" in pos_id else pos_id,
                        external_id=modifier_starter_external_id_map.get(str(starter_id)),
                        min_amount=pos_id.split("/")[1] if "/" in pos_id else None,
                        max_amount=pos_id.split("/")[2] if "/" in pos_id else None,
                        starter_id=starter_id,
                        client_id=client.id,
                    )
                    for pos_id, starter_id in client_menu.get("modifiers", {}).items()
                    if not pos_id.isdigit()
                ]
                modifier_groups = [
                    ModifierGroup(
                        pos_id=pos_id.split("/")[0] if "/" in pos_id else pos_id,
                        starter_id=starter_id,
                        client_id=client.id,
                        min_amount=pos_id.split("/")[1] if "/" in pos_id else None,
                        max_amount=pos_id.split("/")[2] if "/" in pos_id else None,
                    )
                    for pos_id, starter_id in client_menu.get("modifier_groups", {}).items()
                ]
                meals = [
                    Meal(external_id=pos_id, pos_id=pos_id, starter_id=starter_id, client_id=client.id)
                    if pos_id.isdigit()
                    else Meal(pos_id=pos_id, starter_id=starter_id, client_id=client.id)
                    for pos_id, starter_id in client_menu.get("meals", {}).items()
                ]

                session.add_all(categories)
                session.add_all(modifiers)
                session.add_all(modifier_groups)
                session.add_all(meals)
                session.flush()

                meal_pos_domain_id_map: dict[str, int] = {meal.pos_id: meal.id for meal in meals}

                for shop_pos_id, shop_menu_data in client_menu.get("shops", {}).items():
                    shop_id = shop_pos_domain_id_map[shop_pos_id]
                    meal_offers = [
                        MealOffer(
                            shop_id=shop_id,
                            meal_id=meal_pos_domain_id_map[meal_pos_id],
                            pos_id=meal_pos_id,
                            starter_id=meal_offer_starter_id,
                        )
                        for meal_pos_id, meal_offer_starter_id in shop_menu_data.get("meals", {}).items()
                    ]

                    session.add_all(meal_offers)

        session.commit()
        print("Finish migrate")


@cli.command(name="transfer")
def transfer_menu_to_project() -> None:
    print("Start transfer")
    transfer_client_menu_to_project()
    print("Finish transfer")


if __name__ == "__main__":
    cli()
