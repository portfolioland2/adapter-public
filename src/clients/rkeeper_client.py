import json
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

import httpx
from httpx import Response
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from src.config import settings
from src.logger import get_logger
from src.models import Client
from src.schemas.rkeeper import (
    OrderDraft,
    RKeeperMenu,
    RKeeperOrder,
    RKeeperOrderStatus,
    RKeeperShop,
    RKeeperLimitedListItem,
)

logger = get_logger("rkeeper_client")
tracer = trace.get_tracer("rkeeper")


class RkeeperClientError(Exception):
    def __init__(self, message: str = "") -> None:
        super().__init__(f"Ошибка в Rkeeper: {message}")


class RkeeperClientInvalidError(RkeeperClientError):
    pass


class ShopMenuParseError(Exception):
    pass


class RkeeperClient:
    """
    https://docs.rkeeper.ru/delivery/dejstviya-s-zakazami-10819423.html
    """

    def __init__(self, client: Client) -> None:
        self.client = client
        self.base_url = "https://delivery.ucs.ru/orders/api/v1/"
        self._token: str = ""
        self._token_expired_at: datetime = datetime.now()

    @property
    def token(self) -> str:
        if self._token_expired_at < datetime.now():
            self._set_token()

        return self._token

    def get_menu(self, shop_id: str) -> RKeeperMenu:
        url = urljoin(self.base_url, "menu/view")
        params = {"restaurantId": shop_id}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        try:
            with tracer.start_as_current_span("rkeeper_menu receive") as span:
                span.set_attribute("client.id", self.client.client_id)
                span.set_attribute("shop.id", shop_id)
                span.set_attribute("rkeeper.menu", json.dumps(data))

            return RKeeperMenu(**data)
        except Exception as e:
            logger.exception("could not parse menu", client_id=self.client.client_id, json=data)
            raise e

    def get_shops(self) -> list[RKeeperShop]:
        url = urljoin(self.base_url, f"orderSources/{self.client.client_id}/restaurants")

        try:
            response = self._fetch(url)
            shops = response.json()["result"]
            logger.info("Get shops", client_id=self.client.client_id, url=url, response=shops)

            return [RKeeperShop(**shop) for shop in shops]
        except httpx.RequestError:
            raise RkeeperClientError
        except Exception as e:
            logger.exception(
                "could not parse shops",
                client_id=self.client.client_id,
                content=response.content,
                shops=shops,
            )
            raise e

    def get_status_of_orders(self) -> list[RKeeperOrderStatus]:
        url = urljoin(self.base_url, "orders")
        response = self._fetch(url)
        orders = response.json()["result"]

        return [RKeeperOrderStatus(**order) for order in orders]

    def preliminary_calculation(self, order: RKeeperOrder) -> OrderDraft:
        url = "orders/delivery"
        response = self._pos_request(url, order).json()
        logger.info(
            "Created order draft",
            json=response,
            url=url,
            token=self.token,
            client_id=self.client.client_id,
            order=order.dict(by_alias=True),
        )
        if "result" in response:
            return OrderDraft(**response["result"]["amount"])
        logger.error(
            "Error order draft",
            json=response,
            url=url,
            token=self.token,
            client_id=self.client.client_id,
        )
        raise RkeeperClientInvalidError(f'errors={response["errors"]} msg={response["msg"]}')

    def create_order(self, order: RKeeperOrder) -> str:
        url = "orders"
        response = self._pos_request(url, order).json()
        logger.info(
            "Created order",
            json=response,
            url=url,
            token=self.token,
            client_id=self.client.client_id,
        )
        if "result" in response:
            return response["result"]["orderId"]

        raise RkeeperClientInvalidError(f'errors={response["errors"]} msg={response["msg"]}')

    def get_limit_list(self) -> list[RKeeperLimitedListItem]:
        with tracer.start_as_current_span("get limit list", kind=SpanKind.CLIENT) as span:
            span.set_attribute("client.id", self.client.client_id)
            url = urljoin(self.base_url, "menu/dishes/limitedlist")
            response = None
            try:
                response = self._fetch(url).json()
                span.set_attribute("response", json.dumps(response))
                limited_list = response.get("result")
                if limited_list is None:
                    raise Exception("No limited list")

                return [RKeeperLimitedListItem(**item) for item in limited_list]

            except httpx.RequestError as err:
                logger.exception(
                    "could not fetch limited list",
                    client_id=self.client.client_id,
                    content=response if response else None,
                    err=str(err),
                )
                return []

            except Exception as e:
                logger.exception(
                    "could not parse limited list",
                    client_id=self.client.client_id,
                    err=str(e),
                )
                return []

    def order_payment(self, order_id: str) -> dict:
        with tracer.start_as_current_span("update order payment", kind=SpanKind.CLIENT) as span:
            url = urljoin(self.base_url, f"orders/{order_id}/pay")
            date = datetime.now()
            data = [
                {
                    "code": self.client.currency_code,
                    "amount": 0.0,
                    "paidAt": date.isoformat(),
                    "name": "",
                }
            ]
            span.set_attribute("body", str(data))
            span.set_attribute("url", url)
            span.set_attribute("order.id", order_id)
            # if bonuses > 0:
            #     data.append(
            #         {
            #             "code": settings.BONUS_CURRENCY_CODE,
            #             "amount": bonuses,
            #             "paidAt": str(date),
            #             "name": "",
            #         }
            #     )

            logger.info(
                f"Sending payment to the rkeeper for order {order_id}", client_id=self.client.client_id, data=data
            )
            response_json = self._put_request(url, data).json()
            logger.info(
                f"The response of the rkeeper about the payment of the order {order_id}",
                client_id=self.client.client_id,
                response_json=response_json,
            )
            return response_json

    def _pos_request(self, url: str, data: RKeeperOrder) -> Response:
        with httpx.Client(base_url=self.base_url, timeout=settings.DEFAULT_TIMEOUT) as client:
            response = client.post(
                url,
                data=data.json(by_alias=True),  # type: ignore
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.token}",
                },
            )
        return response

    def _put_request(self, url: str, data: list) -> Response:
        return httpx.put(
            url,
            json=data,
            timeout=settings.DEFAULT_TIMEOUT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )

    def _set_token(self) -> None:
        url = "https://auth-delivery.ucs.ru/connect/token"
        resp = httpx.post(
            url,
            timeout=settings.DEFAULT_TIMEOUT,
            data={
                "client_id": self.client.client_id,
                "client_secret": self.client.client_secret,
                "grant_type": "client_credentials",
                "scopes": "orders",
            },
        )
        if resp.status_code == 400:
            logger.warn("cannot set token", content=resp.content, client_id=self.client.client_id)
            raise RkeeperClientInvalidError

        data = resp.json()
        self._token = data["access_token"]
        self._token_expired_at = datetime.now() + timedelta(seconds=data["expires_in"])

    def _fetch(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        return httpx.get(
            url, headers={"Authorization": f"Bearer {self.token}"}, params=params, timeout=settings.DEFAULT_TIMEOUT
        )
