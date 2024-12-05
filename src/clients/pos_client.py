import json
from typing import List
from urllib.parse import urljoin

import httpx
from httpx import HTTPStatusError
from opentelemetry import trace
from starlette import status
from starter_dto import pos
from starter_dto.pos.menu import UpdateModifierOffer, CreateModifierOffer

from src.config import settings
from src.logger import get_logger
from src.schemas.order import OrderStatusUpdater

from opentelemetry.trace import SpanKind

logger = get_logger("pos_client")


tracer = trace.get_tracer("rkeeper")


class PosGatewayClientError(Exception):
    pass


class PosGatewayClientInvalidError(PosGatewayClientError):
    pass


class PosGatewayClientForbiddenError(PosGatewayClientError):
    pass


class PosGatewayClient:
    def __init__(self, api_key: str):
        self.base_url = settings.POS_GATEWAY_URL
        self.api_key = api_key

    def create_shops(self, shops: list[pos.CreateShop]) -> pos.ObjectOutList:
        logger.debug(
            "shops for create ",
            shops=[shop.dict() for shop in shops],
            api_key=self.api_key,
        )
        return self._post_request(shops, "shops")

    def update_shops(self, shops: list[pos.UpdateShop]) -> None:
        logger.debug(
            "shops for update",
            shops=[shop.dict() for shop in shops],
            api_key=self.api_key,
        )
        self._put_request(shops, "shops")

    def create_categories(self, categories: list[pos.CreateCategory]) -> pos.ObjectOutList:
        logger.debug(
            "categories for create ",
            categories=[i.dict() for i in categories],
            api_key=self.api_key,
        )
        return self._post_request(categories, "categories")

    def update_categories(self, categories: list[pos.UpdateCategory]) -> None:
        logger.debug(
            "categories for update ",
            categories=[i.dict() for i in categories],
            api_key=self.api_key,
        )
        self._put_request(categories, "categories")

    def create_meals(self, meals: list[pos.CreateMeal]) -> pos.ObjectOutList:
        logger.debug(
            "meals for create ",
            meals=[meal.dict() for meal in meals],
            api_key=self.api_key,
        )
        return self._post_request(meals, "meals")

    def update_meals(self, meals: list[pos.UpdateMeal]) -> None:
        logger.debug(
            "meals for update ",
            meals=[meal.dict() for meal in meals],
            api_key=self.api_key,
        )
        self._put_request(meals, "meals")

    def create_meal_offers(
        self, meal_offers: list[pos.menu.CreateMealOffer], shop_starter_id: int
    ) -> pos.ObjectOutList:
        logger.debug(
            "meal offers for create ",
            meal_offers=[meal_offer.dict() for meal_offer in meal_offers],
            api_key=self.api_key,
        )
        with tracer.start_as_current_span("update meal offers in gateway") as span:
            span.set_attribute("shop.starter.id", shop_starter_id)
            span.set_attribute("api.key", self.api_key)
            span.set_attribute("meal.offers", json.dumps([offer.dict(by_alias=True) for offer in meal_offers]))

            created_gateway_offers = self._post_request(meal_offers, f"shop/{shop_starter_id}/meals")
            span.set_attribute(
                "meal.offers",
                json.dumps([created_offer.dict(by_alias=True) for created_offer in created_gateway_offers.data]),
            )
            return created_gateway_offers

    def update_meal_offers(self, meal_offers: list[pos.menu.UpdateMealOffer], shop_starter_id: int) -> None:
        logger.debug(
            "meal offers for update",
            meal_offers=[meal_offer.dict() for meal_offer in meal_offers],
            api_key=self.api_key,
        )
        with tracer.start_as_current_span("update meal offers in gateway") as span:
            span.set_attribute("shop.starter.id", shop_starter_id)
            span.set_attribute("api.key", self.api_key)
            span.set_attribute("meal.offers", json.dumps([offer.dict(by_alias=True) for offer in meal_offers]))

            self._put_request(meal_offers, f"shop/{shop_starter_id}/meals")

    def create_modifier_groups(self, modifier_groups: list[pos.CreateModifierGroup]) -> pos.ObjectOutList:
        logger.debug(
            "modifier groups for create ",
            modifier_groups=[modifier_group.dict() for modifier_group in modifier_groups],
            api_key=self.api_key,
        )
        return self._post_request(modifier_groups, "modifier_groups")

    def update_modifier_groups(self, modifier_groups: list[pos.UpdateModifierGroup]) -> None:
        logger.debug(
            "modifier groups for update ",
            modifier_groups=[modifier_group.dict() for modifier_group in modifier_groups],
            api_key=self.api_key,
        )
        self._put_request(modifier_groups, "modifier_groups")

    def create_modifiers(self, modifiers: list[pos.CreateModifier]) -> pos.base.ObjectOutList:
        logger.debug(
            "modifiers for create ",
            modifiers=[modifier.dict() for modifier in modifiers],
            api_key=self.api_key,
        )
        return self._post_request(modifiers, "modifiers")

    def update_modifiers(self, modifiers: list[pos.UpdateModifier]) -> None:
        logger.debug(
            "modifiers for update",
            modifiers=[modifier.dict() for modifier in modifiers],
            api_key=self.api_key,
        )
        self._put_request(modifiers, "modifiers")

    def update_modifier_offers(self, modifier_offers: list[UpdateModifierOffer]) -> None:
        logger.debug(
            "modifier offers for update",
            modifiers=[modifier.dict() for modifier in modifier_offers],
            api_key=self.api_key,
        )
        self._put_request(modifier_offers, "modifier_offer")

    def create_modifier_offers(self, modifier_offers: list[CreateModifierOffer]) -> pos.base.ObjectOutList:
        logger.debug(
            "modifier offers for create",
            modifiers=[modifier.dict() for modifier in modifier_offers],
            api_key=self.api_key,
        )
        return self._post_request(modifier_offers, "modifier_offer")

    def register_webhook(self) -> None:
        url = urljoin(self.base_url, "set_webhook")
        try:
            response = httpx.post(
                url,
                json={"callbackUrl": f"https://{settings.EXTERNAL_HOST}/api/order"},
                headers={"Authorization": self.api_key},
            )
            logger.info(
                "register webhook",
                status=response.status_code,
                url=url,
                api_key=self.api_key,
                content=response.content,
            )
            if response.status_code == status.HTTP_403_FORBIDDEN:
                raise PosGatewayClientForbiddenError

            response.raise_for_status()
        except HTTPStatusError as e:
            logger.warn(
                "Gateway is not responding: ",
                status=e.response.status_code,
                url=url,
                api_key=self.api_key,
                content=e.response.content,
            )
            raise PosGatewayClientError
        except httpx.RequestError:
            raise PosGatewayClientError

    def register_webhook_for_settings(self) -> None:
        url = urljoin(self.base_url, "adapter/webhook")
        response = httpx.post(
            url,
            json={"callbackUrl": f"https://{settings.EXTERNAL_HOST}/api/project"},
            headers={"Authorization": self.api_key},
        )
        logger.info(
            "register webhook for settings",
            status=response.status_code,
            url=url,
            api_key=self.api_key,
            content=response.content,
        )

    def update_status_of_orders(self, status_of_orders: list[OrderStatusUpdater]) -> None:
        logger.debug("update status_of_orders", status_of_orders=status_of_orders)
        with httpx.Client(base_url=self.base_url, timeout=10, headers={"Authorization": self.api_key}) as client:
            for status_order in status_of_orders:
                with tracer.start_as_current_span("send order status to pos gateway") as span:
                    span.set_attribute("order.id", status_order.id)
                    span.set_attribute("order.pos_number", status_order.pos_number)
                    span.set_attribute("status", status_order.status)
                    url = f"order/{status_order.id}/status"
                    client.patch(url=url, json=status_order.dict(by_alias=True, exclude={"id"}))

    def _post_request(self, create_data: list, url: str) -> pos.ObjectOutList:
        try:
            response = httpx.post(
                urljoin(self.base_url, url),
                json=[i.dict(by_alias=True) for i in create_data],
                headers={"Authorization": self.api_key},
            )

            if response.status_code == 403:
                raise PosGatewayClientInvalidError

            json = response.json()
            if "data" in json:
                logger.info("Created data", data=json["data"], api_key=self.api_key)
                return pos.ObjectOutList(data=json["data"], count=0)

            logger.warn(
                "Empty data",
                json=json,
                response=response,
                text=response.text,
                api_key=self.api_key,
            )

            return pos.ObjectOutList(data=[], count=0)
        except httpx.RequestError:
            raise PosGatewayClientError

    def _put_request(self, update_objects: List, url: str) -> None:
        try:
            response = httpx.put(
                url=urljoin(self.base_url, url),
                json=[i.dict(by_alias=True) for i in update_objects],
                headers={"Authorization": self.api_key},
            )

            if response.status_code == 403:
                logger.info("wrong api_key", content=response.content, api_key=self.api_key)
                raise PosGatewayClientInvalidError
            elif response.status_code == 404:
                pass
        except httpx.RequestError:
            raise PosGatewayClientError
