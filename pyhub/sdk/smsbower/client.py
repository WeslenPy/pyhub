from typing import Optional, List, Dict, Any
from pyhub.sdk.base.client import ClientBase
from pyhub.sdk.base.schemas import CountryPrices, ServicePrice


class SMSBowerClient(ClientBase):
    """
    Client for SMSBowerClient
    """

    def __init__(
        self,
        api_key: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        base_url: str = "https://smsbower.page/stubs/handler_api.php"
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout
        )

    def get_prices(
        self, 
        service: Optional[str] = None, 
        country: Optional[int] = None,
        free_price: Optional[bool] = False
    ) -> List[CountryPrices]:
        """
        Overrides get_prices to use get_prices_v2 for SMSBower,
        as it provides more detailed data.
        """
        return self.get_prices_v2(service=service, country=country)

    def get_prices_v2(self, service: Optional[str] = None, country: Optional[int] = None) -> List[CountryPrices]:
        """
        Get prices for services (V2).
        Returns multiple prices per service.
        """
        params = {}
        if service:
            params["service"] = service
        if country is not None:
            params["country"] = country

        response = self._request("getPricesV2", params=params)
        try:
            import json
            data = json.loads(response)
            return self._parse_complex_prices(data, version="v2")
        except Exception as e:
            raise ValueError(f"Error parsing prices V2: {response[:200]}... Internal error: {str(e)}")

    def get_prices_v3(self, service: Optional[str] = None, country: Optional[int] = None) -> List[CountryPrices]:
        """
        Get prices for services (V3).
        Returns provider-specific data.
        """
        params = {}
        if service:
            params["service"] = service
        if country is not None:
            params["country"] = country

        response = self._request("getPricesV3", params=params)
        try:
            import json
            data = json.loads(response)
            return self._parse_complex_prices(data, version="v3")
        except Exception as e:
            raise ValueError(f"Error parsing prices V3: {response[:200]}... Internal error: {str(e)}")

    def _parse_complex_prices(self, data: Dict[str, Any], version: str) -> List[CountryPrices]:
        """ Helper to parse V2 and V3 structures into standardized CountryPrices. """
        result = []
        for country_id, services in data.items():
            service_map = {}
            for srv_code, srv_data in services.items():
                prices = []
                total_count = 0
                
                if version == "v2":
                    # format: {"price1": count, "price2": count}
                    for price_str, count in srv_data.items():
                        p = float(price_str)
                        prices.append(p)
                        total_count += int(count)
                else:
                    # version v3 format: {"provider_id": {"price": price, "count": count}}
                    for provider_data in srv_data.values():
                        p = float(provider_data.get("price", 0))
                        prices.append(p)
                        total_count += int(provider_data.get("count", 0))

                if prices:
                    prices.sort()
                    service_map[srv_code] = ServicePrice(
                        service=srv_code,
                        cost=prices if len(prices) > 1 else prices[0],
                        min_price=prices[0],
                        max_price=prices[-1],
                        count=total_count
                    )
            
            if service_map:
                result.append(CountryPrices(country_id=int(country_id), services=service_map))
        
        return result
