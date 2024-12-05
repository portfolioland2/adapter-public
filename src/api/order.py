from fastapi import (
    APIRouter,
    Depends,
)
from opentelemetry import trace
from opentelemetry.propagators.jaeger import JaegerPropagator  # type: ignore
from opentelemetry.trace import SpanKind

from src import deps
from src.api.schemas import OrderWithCtx, OrderCreatedApi
from sqlalchemy.orm import Session

from src.core.repositories.order import OrderRepository
from src.logger import get_logger
from src.models import Client
from src.services.order import OrderService
from src.services.redis_client import Storage

order_router = APIRouter(tags=["order"])
logger = get_logger("api")
tracer = trace.get_tracer("api")


storage = Storage()


@order_router.post("/order", response_model=OrderCreatedApi)
def create_order(
    starter_order: OrderWithCtx,
    client: Client = Depends(deps.get_client_by_api_key),
    db: Session = Depends(deps.get_db),
) -> OrderCreatedApi:
    log = logger.bind(
        order_id=starter_order.starter_id,
        order_global_id=starter_order.global_id,
        client_id=client.client_id,
    )
    log.info("Received order from gateway")
    ctx = JaegerPropagator().extract(starter_order.ctx)

    with tracer.start_as_current_span("order receive", kind=SpanKind.SERVER, context=ctx) as span:
        span.set_attribute("order.id", starter_order.starter_id)
        span.set_attribute("order.global_id", starter_order.global_id)
        span.set_attribute("order.data", starter_order.json(by_alias=True))
        cached = storage.get_order_cached(starter_order.global_id)
        span.set_attribute("cached", cached)
        log.info("Cached order", cached=cached)
        if cached:
            return OrderCreatedApi(order_id=starter_order.global_id)

        storage.set_order_cache(starter_order.global_id)

        order = OrderRepository(db).get_order_by_client_and_starter_id(client.id, starter_order.global_id)
        if order:
            order_to_return = OrderCreatedApi(order_id=starter_order.global_id)
            log.info("Return Order", order_to_return=order_to_return.json(by_alias=True))
            return order_to_return

        rkeeper_order_id = OrderService(db, client, log).create_order(starter_order)
        db.commit()
        return OrderCreatedApi(order_id=rkeeper_order_id)
