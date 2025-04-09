import json
from datetime import datetime, timedelta
from typing import Optional, Any, List, Dict, Union
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

logger = get_logger("sbis_client")
tracer = trace.get_tracer("sbis")


class RkeeperClientError(Exception):
    def __init__(self, message: str = "") -> None:
        super().__init__(f"Ошибка в СБИС: {message}")


class RkeeperClientInvalidError(RkeeperClientError):
    pass


class ShopMenuParseError(Exception):
    pass


class SBISClient:
    """
    https://saby.ru/help/integration/api/app_presto
    """

    def __init__(self, client: Client) -> None:
        self.client = client
        self.base_url = "https://api.sbis.ru/retail/"
        self._token: str = ""

    @property
    def token(self) -> str:
        if not hasattr(self, '_token') or self._token == "":
            self._set_token()

        return self._token

    def get_menu(self, shop_id: str) -> SBISMenu:
        url = urljoin(self.base_url, "nomenclature/price-list")
        params = {"pointId": shop_id}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        try:
            with tracer.start_as_current_span("sbis_menu receive") as span:
                span.set_attribute("client.id", self.client.client_id)
                span.set_attribute("shop.id", shop_id)
                span.set_attribute("sbis.menu", json.dumps(data))

            return SBISMenu(**data)
        except Exception as e:
            logger.exception("could not parse menu", client_id=self.client.client_id, json=data)
            raise e
    def get_meals(self, shop_id: str, price_list_id: str) -> SBISMenu:
        url = urljoin(self.base_url, "nomenclature/list")
        params = {"pointId": shop_id, "priceListId": price_list_id}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        try:
            with tracer.start_as_current_span("sbis_menu receive") as span:
                span.set_attribute("client.id", self.client.client_id)
                span.set_attribute("shop.id", shop_id)
                span.set_attribute("sbis.menu", json.dumps(data))

            return RKeeperMenu(**data)
        except Exception as e:
            logger.exception("could not parse menu", client_id=self.client.client_id, json=data)
            raise e

    def get_district(self, shop_id: str) -> Any:
        url = urljoin(self.base_url, "district/list")
        params = {"pointId": shop_id}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        return data

    def get_delivery_cost(self, shop_id: str, address: str | dict[str, Any]) -> Any:
        url = urljoin(self.base_url, "district/list")
        params = {"pointId": shop_id, "address": address}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        return data

    def get_delivery_eta(self, shop_id: str) -> Any:
        url = urljoin(self.base_url, "delivery/calendar")
        params = {"pointId": shop_id}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        return data

    def get_delivery_suggested(self, entered_address: str) -> Any:
        url = urljoin(self.base_url, "delivery/suggested-address")
        params = {"enteredAddress": entered_address}
        response = self._fetch(url, params)
        response.raise_for_status()

        data = response.json()["result"]
        return data

    def create_order(self, order: RKeeperOrder) -> str:
        url = "order/create"
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
                    "X-SBISAccessToken": f"{self.token}",
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
                "X-SBISAccessToken": f"{self.token}",
            },
        )

    def _set_token(self) -> None:
        url = "https://online.sbis.ru/oauth/service/"
        resp = httpx.post(
            url,
            timeout=settings.DEFAULT_TIMEOUT,
            data={
                "app_client_id": self.client.client_id,
                "app_secret": self.client.client_secret,
                "secret_key": self.client.secret_key
            },
        )
        if resp.status_code == 400:
            logger.warn("cannot set token", content=resp.content, client_id=self.client.client_id)
            raise RkeeperClientInvalidError

        data = resp.json()
        self._token = data["token"]

    def _fetch(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        return httpx.get(
            url, headers={"X-SBISAccessToken": f"{self.token}"}, params=params, timeout=settings.DEFAULT_TIMEOUT
        )
