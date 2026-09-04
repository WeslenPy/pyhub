import json
import httpx
from typing import Optional, List
from loguru import logger
from pyhub.sdk.base.client import ClientBase
from pyhub.sdk.base.schemas import CountryPrices, ReactivationResult, ReactivationOption


class HeroSMSClient(ClientBase):
    """
    Client for HeroSMS API.
    Compatible with SMS-Activate protocol.
    """

    def __init__(
        self,
        api_key: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        base_url: str = "https://hero-sms.com/stubs/handler_api.php"
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout
        )

    async def _post_activation_request(self, action: str, params: dict) -> ReactivationResult:
        """
        Shared POST request logic for HeroSMS actions that return an
        activation-shaped JSON object (reactivate, prolong).
        """
        query_params = {
            "api_key": self.api_key,
            "action": action,
            **params,
        }

        logger.debug(f"Query: {query_params} URL: {self.base_url}")

        async with httpx.AsyncClient(**self.client_kwargs) as client:
            response = await client.post(self.base_url, params=query_params)
            response.raise_for_status()
            text = response.text

            logger.debug(f"URL Full: {response.url}")
            logger.debug(f"Response: {text}")

            errors = ["BAD_KEY", "ERROR_SQL", "BAD_ACTION", "WRONG_ACTIVATION_ID", "NO_KEY", "BANNED"]
            for err in errors:
                if err in text:
                    raise ValueError(f"API Error: {text}")

            try:
                data = json.loads(text)
                return ReactivationResult(
                    activation_id=data["activationId"],
                    phone_number=data["phoneNumber"],
                    activation_cost=data.get("activationCost"),
                    currency=data.get("currency"),
                    country_code=data.get("countryCode"),
                    country_phone_code=data.get("countryPhoneCode"),
                    can_get_another_sms=data.get("canGetAnotherSms"),
                    activation_time=data.get("activationTime"),
                    activation_end_time=data.get("activationEndTime"),
                    activation_operator=data.get("activationOperator"),
                    verification_type=data.get("verificationType"),
                    subtype=data.get("subtype"),
                    service_code=data.get("serviceCode"),
                    status=data.get("status"),
                )
            except Exception as e:
                raise ValueError(f"Error parsing {action} response: {text[:200]}... Internal error: {str(e)}")

    async def reactivate(self, activation_id: str) -> ReactivationResult:
        """
        Reactivate a previously used number (HeroSMS-specific).
        Action: reactivate (POST)
        """
        return await self._post_activation_request("reactivate", {"id": activation_id})

    async def prolong(self, activation_id: str, duration: int) -> ReactivationResult:
        """
        Extend the rental duration of a number (HeroSMS-specific).
        Action: prolong (POST)
        """
        return await self._post_activation_request("prolong", {"id": activation_id, "duration": duration})

    async def _get_options_request(self, action: str, activation_id: str) -> List[ReactivationOption]:
        """
        Shared GET request logic for HeroSMS actions that return a list of
        price/duration options (reactivateOptions, prolongOptions).
        """
        params = {"id": activation_id}
        response = await self._request(action, params=params)

        try:
            data = json.loads(response)
            options = data.get("data", {}).get("options", [])
            return [ReactivationOption(**opt) for opt in options]
        except Exception as e:
            raise ValueError(f"Error parsing {action} response: {response[:200]}... Internal error: {str(e)}")

    async def reactivate_options(self, activation_id: str) -> List[ReactivationOption]:
        """
        Get available reactivation options (price/duration) for a number (HeroSMS-specific).
        Action: reactivateOptions
        """
        return await self._get_options_request("reactivateOptions", activation_id)

    async def prolong_options(self, activation_id: str) -> List[ReactivationOption]:
        """
        Get available rental prolongation options (price/duration) for a number (HeroSMS-specific).
        Action: prolongOptions
        """
        return await self._get_options_request("prolongOptions", activation_id)

#deprecated
   # async def get_prices(self, service: Optional[str] = None, country: Optional[int] = None,free_price: Optional[bool] = True) -> List[CountryPrices]:
     #  """
    #    Overrides get_prices to use getTopCountriesByService for HeroSMS,
    #    as it provides more detailed data including country mapping.
   #     """

   #     results = await self.get_top_countries_by_service(service=service,free_price=free_price)
    
    #    if country is not None:
      #      return [r for r in results if r.country_id == country]
            
    #    return results


        # results = super().get_prices(service=service,country=country,free_price=free_price)

        # return results
