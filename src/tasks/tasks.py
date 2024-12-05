from typing import Any

from celery import (
    Celery,
    Task,
)
from celery.schedules import crontab
from celery.signals import worker_process_init
from httpx import HTTPStatusError
from opentelemetry.instrumentation.celery import CeleryInstrumentor  # type: ignore

from src.clients.pos_client import (
    PosGatewayClientError,
    PosGatewayClientInvalidError,
)
from src.clients.rkeeper_client import (
    RkeeperClientError,
    RkeeperClientInvalidError,
    RkeeperClient,
)
from src.config import settings
from src.core.repositories.client import ClientRepository
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.logger import get_logger
from src.services.transfer_menu_from_client_to_project import MenuTransfer
from src.tasks.sync import (
    Sync,
)
from src.tracer import init_tracer

logger = get_logger("client")


class DBTask(Task):
    _db = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def run(self, *args: Any, **kwargs: Any) -> None:
        pass


@worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):  # type: ignore
    init_tracer()
    CeleryInstrumentor().instrument()


app = Celery(
    "tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs) -> None:  # type: ignore
    sender.add_periodic_task(
        crontab(minute="*/20"),
        sync_shops.s(),
    )
    sender.add_periodic_task(
        crontab(minute="*/5"),
        sync_menu.s(),
    )
    sender.add_periodic_task(
        crontab(minute="*"),
        sync_status_of_orders.s(),
    )


@app.task(bind=True, base=DBTask)
def sync_shops(self: DBTask, client_id: str | None = None) -> None:
    logger.info("Sync of shops has begun")

    client_repo = ClientRepository(self.db)
    clients = [client_repo.get_client_by_client_id(client_id)] if client_id else client_repo.get_active_clients()
    for client in clients:  # type: ignore
        logger.info(f"Sync of shops for client_id: {client.client_id}")
        try:
            Sync(self.db, client).shops()
            self.db.commit()
        except (PosGatewayClientError, RkeeperClientError) as e:
            logger.error(str(e))
            raise self.retry(countdown=5, max_retries=3)
        except (
            RkeeperClientInvalidError,
            PosGatewayClientInvalidError,
            Exception,
        ) as e:
            logger.error(str(e))
            continue
    logger.info("Sync of shops is finished")


@app.task(bind=True, base=DBTask)
def sync_menu(self: DBTask, client_id: str | None = None) -> None:
    logger.info("Sync of menu has begun")
    client_repo = ClientRepository(self.db)
    clients = [client_repo.get_client_by_client_id(client_id)] if client_id else client_repo.get_active_clients()
    for client in clients:
        if not client.project_id:
            logger.info(f"Client is not part of project", client_id=client.client_id)
            continue

        logger.info(f"Sync of menu for client_id: {client.client_id}")
        log = logger.bind(client_id=client.client_id, stream="sync_menu")
        sync = Sync(self.db, client, log)
        try:
            for shop in client.shops:
                try:
                    log.info("Start sync shop menu", shop=shop.pos_id)
                    sync.menu(shop.pos_id)
                    self.db.commit()
                except HTTPStatusError:
                    logger.exception("Error while parsing menu", client_id=client.client_id)
                    continue
        except (
            RkeeperClientInvalidError,
            PosGatewayClientError,
            RkeeperClientError,
            PosGatewayClientInvalidError,
            Exception,
        ) as e:
            logger.exception("Error while sync", e=str(e), client_id=client_id)
            continue
    logger.info("Sync of menu is finished")


@app.task(bind=True, base=DBTask)
def sync_status_of_orders(self: DBTask) -> None:
    logger.info("Sync status orders has started")
    client_repo = ClientRepository(self.db)
    for client in client_repo.get_active_clients():
        logger.info(f"Sync status orders for client_id: {client.client_id}")
        try:
            Sync(self.db, client).status_orders()
            self.db.commit()
        except (
            RkeeperClientInvalidError,
            PosGatewayClientError,
            RkeeperClientError,
            PosGatewayClientInvalidError,
            Exception,
        ) as e:
            logger.exception("Error while status orders", e=str(e), client_id=client.client_id)
            continue

    logger.info("Sync status orders is finished")


@app.task(bind=True, base=DBTask)
def transfer_client_menu_to_project(self: DBTask, client_id: str | None = None) -> None:
    log = logger.bind(client_id=client_id, stream="transfer_menu")
    log.info(f"Start")
    client_repo = ClientRepository(self.db)
    clients = [client_repo.get_client_by_client_id(client_id)] if client_id else client_repo.get_active_clients()
    if not clients:
        log.error(f"Client not found", client_id=client_id)
        return

    for client in clients:
        if not client.project_id:
            continue

        shops = client_repo.get_shops(client.id)
        keeper_client = RkeeperClient(client)

        for shop in shops:
            log.info(f"Transfer menu for shop", shop_pos_id=shop.pos_id)
            try:
                try:
                    keeper_menu = keeper_client.get_menu(shop.pos_id)
                except HTTPStatusError as e:
                    log.error(e)
                    continue

                menu_transfer = MenuTransfer(self.db, client, keeper_menu)

                menu_transfer.transfer_modifiers()
                menu_transfer.transfer_modifier_groups()
                menu_transfer.transfer_meals()
                self.db.commit()
                logger.info("Shop Transfer menu is finished", shop_pos_id=shop.pos_id)
            except (
                RkeeperClientInvalidError,
                PosGatewayClientError,
                RkeeperClientError,
                PosGatewayClientInvalidError,
                Exception,
            ) as e:
                log.error(e)
                continue

        sync_shops.delay(client_id=client.client_id)
        app.send_task("src.tasks.tasks.sync_menu", args=(client.client_id,), countdown=10)
