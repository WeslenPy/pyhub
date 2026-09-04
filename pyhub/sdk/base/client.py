import asyncio
import json
import httpx
import re
from typing import Optional, Dict, Any, List, Union
from .schemas import Balance, NumberActivation, ActivationStatus, ServicePrice, CountryPrices, Service
from loguru import logger


class ClientBase:
    """
    Base generic async client for SMSHub-like APIs.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.proxy = proxy
        self.timeout = timeout

        self.client_kwargs: Dict[str, Any] = {
            "timeout": self.timeout,
            "follow_redirects": True,
        }

        if self.proxy:
            self.client_kwargs["proxy"] = self.proxy

    async def _request(self, action: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generic request method for SMSHub API actions.
        """
        if params is None:
            params = {}

        query_params = {
            "api_key": self.api_key,
            "action": action,
            **params
        }

        logger.debug(f"Query: {query_params} URL: {self.base_url}")

        async with httpx.AsyncClient(**self.client_kwargs) as client:
            response = await client.get(self.base_url, params=query_params)
            response.raise_for_status()
            text = response.text

            logger.debug(f"URL Full: {response.url}")

            logger.debug(f"Response: {text}")

            errors = ["BAD_KEY", "ERROR_SQL", "BAD_ACTION", "WRONG_ACTIVATION_ID", "NO_KEY", "BANNED"]
            for err in errors:
                if err in text:
                    raise ValueError(f"API Error: {text}")

            return text

    async def get_balance(self) -> Balance:
        """Get account balance."""
        response = await self._request("getBalance")
        if ":" in response:
            amount = float(response.split(":")[1])
            return Balance(amount=amount)
        raise ValueError(f"Unexpected balance response: {response}")

    async def get_number(
        self,
        service: str,
        country: Optional[int] = None,
        operator: Optional[str] = None,
        max_price: Optional[str] = None,
    ) -> NumberActivation:
        """Order a number for a service."""
        params = {"service": service}
        if country is not None:
            params["country"] = country
        if operator:
            if country != None and country != 73:
                operator = "any"
            params["operator"] = operator

        if max_price:
            params["maxPrice"] = max_price

        response = await self._request("getNumber", params=params)
        if response.startswith("ACCESS_NUMBER"):
            parts = response.split(":")
            return NumberActivation(
                activation_id=parts[1],
                phone_number=parts[2],
                service=service
            )
        raise ValueError(f"Error getting number: {response}")

    async def set_status(self, activation_id: str, status: int) -> str:
        """Set activation status.

            1 — SMS sent (inform about readiness to receive code)
            3 — request resending of SMS
            6 — complete activation (code received and confirmed)
            8 — cancel activation (return money)
        """
        params = {"id": activation_id, "status": status}
        return await self._request("setStatus", params=params)

    async def active_status(self, activation_id: str) -> str:
        """Shortcut to set status to 1 (ready)."""
        return await self.set_status(activation_id, 1)

    async def reactivation_number(self, activation_id: str) -> NumberActivation:
        """
        Request reactivation of a previously used number.
        Action: getExtraActivation
        """
        params = {"activationId": activation_id}
        response = await self._request("getExtraActivation", params=params)

        if response.startswith("ACCESS_NUMBER"):
            parts = response.split(":")
            new_id = parts[1]
            new_number = parts[2]

            await self.active_status(new_id)

            return NumberActivation(
                activation_id=new_id,
                phone_number=new_number,
                service="reactivation"
            )
        raise ValueError(f"Error reactivating number: {response}")

    async def get_status(self, activation_id: str) -> ActivationStatus:
        """Get activation status and SMS code."""
        params = {"id": activation_id}
        response = await self._request("getStatus", params=params)

        if ":" in response:
            status, code = response.split(":", 1)
            return ActivationStatus(status=status, code=code)

        return ActivationStatus(status=response)

    async def get_sms(
        self,
        activation_id: str,
        timeout: int = 0,
        interval: int = 5,
    ) -> Optional[str]:
        """
        Polls for SMS code until it arrives or timeout is reached.

        Args:
            activation_id: ID of the activation
            timeout: Maximum wait time in seconds (0 = single poll)
            interval: Time between polls in seconds
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout if timeout > 0 else None

        while True:
            status = await self.get_status(activation_id)
            if status.status == "STATUS_OK":
                return status.code

            if status.status in ["STATUS_CANCEL", "NO_ACTIVATION", "ACCESS_CANCEL"]:
                return None

            if deadline is None:
                return None

            if loop.time() >= deadline:
                return None

            await asyncio.sleep(interval)

    async def get_new_sms(self, activation_id: str, timeout: int = 60, interval: int = 5) -> Optional[str]:
        """
        Requests a new SMS for the same number (resend) and waits for it.
        Useful when you need a second code from the same number.
        """
        await self.set_status(activation_id, 3)
        return await self.get_sms(activation_id, timeout=timeout, interval=interval)

    async def get_prices(
        self,
        service: Optional[str] = None,
        country: Optional[int] = None,
        free_price: Optional[bool] = False
    ) -> List[CountryPrices]:
        """
        Get prices for services.
        This usually returns a complex JSON.
        """
        params = {}
        if service:
            params["service"] = service
        if country is not None:
            params["country"] = country
        if free_price:
            params["freePrice"] = True

        response = await self._request("getPrices", params=params)
        try:
            data = json.loads(response)

            result = []

            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                data = data[0]

            if isinstance(data, dict):
                for country_id, services in data.items():
                    if not isinstance(services, dict):
                        continue

                    service_map = {}
                    for srv_code, srv_data in services.items():
                        if not isinstance(srv_data, dict):
                            continue

                        base_cost = float(srv_data.get("cost", 0) or srv_data.get("price", 0))
                        cost: Union[float, List[float]] = base_cost
                        min_p = base_cost
                        max_p = base_cost
                        min_price_disp = base_cost
                        max_price_disp = base_cost

                        count_min_price = int(srv_data.get("count", 0) or 0)
                        count_max_price = count_min_price

                        free_price_map = srv_data.get("freePriceMap")

                        # Some providers (e.g. globalsim) return the price map
                        # directly as srv_data, e.g. {"5.8": 540}, with no
                        # "cost"/"price"/"freePriceMap" wrapper keys.
                        if free_price_map is None and "cost" not in srv_data and "price" not in srv_data:
                            free_price_map = srv_data

                        if isinstance(free_price_map, dict) and free_price_map:
                            prices = sorted(free_price_map.items())
                            if prices:
                                for price, qtd in prices:
                                    if qtd > 0:
                                        cost = price
                                        min_price_disp = price
                                        count_min_price = qtd or 0
                                        break

                                min_p = prices[0][0]
                                max_p = prices[-1][0]
                                count_max_price = prices[-1][1] or 0

                                max_price_disp = max_p

                        service_map[srv_code] = ServicePrice(
                            service=srv_code,
                            cost=cost,
                            min_price=min_p,
                            max_price=max_p,
                            min_price_disp=min_price_disp,
                            max_price_disp=max_price_disp,
                            count_max_price=count_max_price,
                            count_min_price=count_min_price,
                            count=int(srv_data.get("count", count_min_price) or 0)
                        )

                    if service_map:
                        result.append(CountryPrices(country_id=int(country_id), services=service_map))
            return result
        except Exception:
            raise ValueError(f"Error parsing prices or received error: {response}")

    async def get_top_countries_by_service(self, service: Optional[str] = None, free_price: Optional[bool] = False) -> List[CountryPrices]:
        """
        Get top countries for a service or all services.
        Action: getTopCountriesByService
        """
        params = {}
        if service:
            params["service"] = service

        if free_price:
            params["freePrice"] = True

        response = await self._request("getTopCountriesByService", params=params)
        try:
            data = json.loads(response)

            country_map: Dict[int, Dict[str, ServicePrice]] = {}

            def process_entry(srv_code: str, entry: Dict[str, Any]):
                c_id = entry.get("country")
                if c_id is None:
                    return
                c_id = int(c_id)
                if c_id not in country_map:
                    country_map[c_id] = {}

                base_cost = float(entry.get("price", 0) or entry.get("cost", 0) or 0)
                cost: Union[float, List[float]] = base_cost
                min_p = base_cost
                max_p = base_cost
                min_price_disp = base_cost
                max_price_disp = base_cost

                count_min_price = int(entry.get("count", 0) or 0)
                count_max_price = count_min_price

                free_price_map = entry.get("freePriceMap")
                if isinstance(free_price_map, dict) and free_price_map:
                    prices = sorted(free_price_map.items())
                    if prices:
                        for price, qtd in prices:
                            if qtd > 0:
                                cost = price
                                min_price_disp = price
                                count_min_price = qtd or 0
                                break

                        min_p = prices[0][0]
                        max_p = prices[-1][0]
                        count_max_price = prices[-1][1] or 0

                        max_price_disp = max_p

                country_map[c_id][srv_code] = ServicePrice(
                    service=srv_code,
                    cost=cost,
                    min_price=min_p,
                    max_price=max_p,
                    min_price_disp=min_price_disp,
                    max_price_disp=max_price_disp,
                    count_max_price=count_max_price,
                    count_min_price=count_min_price,
                    count=int(entry.get("count", 0) or 0)
                )

            if service:
                entries = data
                if isinstance(data, dict):
                    if service in data:
                        entries = data[service]

                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            process_entry(service, entry)
                elif isinstance(entries, dict):
                    for entry in entries.values():
                        if isinstance(entry, dict):
                            process_entry(service, entry)
            else:
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            for srv_code, entries in item.items():
                                if isinstance(entries, list):
                                    for entry in entries:
                                        process_entry(srv_code, entry)
                                elif isinstance(entries, dict):
                                    for entry in entries.values():
                                        process_entry(srv_code, entry)
                elif isinstance(data, dict):
                    for srv_code, entries in data.items():
                        if isinstance(entries, list):
                            for entry in entries:
                                process_entry(srv_code, entry)
                        elif isinstance(entries, dict):
                            for entry in entries.values():
                                process_entry(srv_code, entry)

            return [CountryPrices(country_id=cid, services=srvs) for cid, srvs in country_map.items()]
        except Exception as e:
            raise ValueError(f"Error parsing top countries: {response[:200]}... Internal error: {str(e)}")

    async def get_services_list(self) -> List[Service]:
        """
        Get list of available services.
        Action: getServicesList
        """
        response = await self._request("getServicesList")
        try:
            data = json.loads(response)

            if data.get("status") != "success":
                raise ValueError(f"API returned non-success status: {response}")

            return [Service(**srv) for srv in data.get("services", [])]
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Error parsing services list: {response[:200]}... Internal error: {str(e)}")
