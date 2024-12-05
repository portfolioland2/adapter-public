import time
from random import randint

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from starlette import status

from src import deps
from src.clients.pos_client import (
    PosGatewayClient,
    PosGatewayClientError,
    PosGatewayClientForbiddenError,
)
from src.core.repositories.client import ClientRepository
from src.core.repositories.schemas.client import ClientCreate, ClientUpdate
from sqlalchemy.orm import Session
from src.deps import get_db
from src.logger import get_logger
from src.models import Client

from src.schemas.rkeeper import Project, RKeeperSettings
from src.tasks.tasks import sync_shops, app

logger = get_logger("api")
project_router = APIRouter(tags=["project"])


@project_router.post("/project", status_code=status.HTTP_204_NO_CONTENT)
def create_project(project: Project, db: Session = Depends(get_db)) -> Response:
    log = logger.bind(project_title=project.project, client_id=project.data.client_id)

    if project.data.client_id == "4895ac22-68ed-4119-b1e4-c1ce01280397":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    # many requests may cause race condition
    jitter = randint(1, 5)
    log.info("jitter time", jitter=jitter)
    time.sleep(jitter)

    log.info("Received project from gateway", data=project.dict())
    client_repo = ClientRepository(db)
    create_client_data = ClientCreate(
        client_id=project.data.client_id,
        client_secret=project.data.client_secret,
        api_key=project.api_key,
        currency_code=project.data.currency_code,
        discount_id=project.data.discount_id,
        is_use_loyalty=project.data.is_use_loyalty,
        is_split_order_items_for_keeper=project.data.is_split_order_items_for_keeper,
        is_use_modifier_external_id=project.data.is_use_modifier_external_id,
        #  TODO: add to next release
        # is_skip_update_order_payment_status=project.data.is_skip_update_order_payment_status,
        # get_modifier_max_amount=project.data.get_modifier_max_amount,
        # is_use_discounts_as_variable=project.data.is_use_discounts_as_variable,
        # is_use_global_modifier_complex=project.data.is_use_global_modifier_complex,
    )
    try:
        client, is_created = client_repo.get_or_create_client(create_client_data, project.project)
        if not is_created:
            logger.info("Client exists", client_id=project.data.client_id)

            return Response(status_code=status.HTTP_204_NO_CONTENT)

        PosGatewayClient(project.api_key).register_webhook()
        db.commit()
        log.info("Project created in RKeeper-adapter")
        sync_shops.delay(client_id=client.client_id)
        app.send_task("src.tasks.tasks.sync_menu", args=(client.client_id,), countdown=10)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except PosGatewayClientForbiddenError:
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    except PosGatewayClientError:
        return Response(status_code=status.HTTP_409_CONFLICT)


@project_router.put("/project", status_code=status.HTTP_204_NO_CONTENT)
def update_project(
    project: RKeeperSettings,
    client: Client = Depends(deps.get_client_by_api_key),
    db: Session = Depends(get_db),
) -> Response:
    log = logger.bind(project_title=project.project_name, client_id=project.client_id)

    if project.client_id == "4895ac22-68ed-4119-b1e4-c1ce01280397":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    # many requests may cause race condition
    jitter = randint(1, 5)
    log.info("jitter time", jitter=jitter)
    time.sleep(jitter)

    log.info("Received project from gateway")
    client_repo = ClientRepository(db)
    try:
        is_client_has_project = bool(client.project_id)
        domain_project, _ = client_repo.get_or_create_project(project.project_name)  # type: ignore
        client_update_data = ClientUpdate(
            currency_code=project.currency_code,
            discount_id=project.discount_id,
            is_use_loyalty=project.is_use_loyalty,
            is_split_order_items_for_keeper=project.is_split_order_items_for_keeper,
            is_use_modifier_external_id=project.is_use_modifier_external_id,
            project_id=domain_project.id,
            #  TODO: add to next release
            # is_skip_update_order_payment_status=project.is_skip_update_order_payment_status,
            # get_modifier_max_amount=project.data.get_modifier_max_amount,
            # is_use_discounts_as_variable=project.data.is_use_discounts_as_variable,
            # is_use_global_modifier_complex=project.data.is_use_global_modifier_complex,
        )
        client_repo.update_client(client.id, client_update_data)
        db.commit()

        if not is_client_has_project:
            app.send_task("src.tasks.tasks.transfer_client_menu_to_project", args=(client.client_id,))

        sync_shops.delay(client_id=client.client_id)
        app.send_task("src.tasks.tasks.sync_menu", args=(client.client_id,), countdown=10)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except PosGatewayClientForbiddenError:
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    except PosGatewayClientError:
        return Response(status_code=status.HTTP_409_CONFLICT)
