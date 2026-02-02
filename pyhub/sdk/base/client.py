import httpx
import re
from typing import Optional, Dict, Any, List, Union
from .schemas import Balance, NumberActivation, ActivationStatus, ServicePrice, CountryPrices
from loguru import logger

class ClientBase:
    """
    Base generic client for SMSHub-like APIs.
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

    def _request(self, action: str, params: Optional[Dict[str, Any]] = None) -> str:
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

        with httpx.Client(**self.client_kwargs) as client:
            response = client.get(self.base_url, params=query_params)
            response.raise_for_status()
            text = response.text
            
            # Common error checks for SMSHub/HeroSMS/SMSActivate
            errors = ["BAD_KEY", "ERROR_SQL", "BAD_ACTION", "WRONG_ACTIVATION_ID", "NO_KEY", "BANNED"]
            for err in errors:
                if err in text:
                    raise ValueError(f"API Error: {text}")
                    
            return text

    def get_balance(self) -> Balance:
        """Get account balance."""
        response = self._request("getBalance")
        # Expected: ACCESS_BALANCE:123.45
        if ":" in response:
            amount = float(response.split(":")[1])
            return Balance(amount=amount)
        raise ValueError(f"Unexpected balance response: {response}")

    def get_number(
        self, 
        service: str, 
        country: Optional[int] = None, 
        operator: Optional[str] = None
    ) -> NumberActivation:
        """Order a number for a service."""
        params = {"service": service}
        if country is not None:
            params["country"] = country
        if operator:
            if country != None and country != 73:
                operator = "any"
            params["operator"] = operator

            
        response = self._request("getNumber", params=params)
        # Expected: ACCESS_NUMBER:ID:NUMBER
        if response.startswith("ACCESS_NUMBER"):
            parts = response.split(":")
            return NumberActivation(
                activation_id=parts[1],
                phone_number=parts[2],
                service=service
            )
        raise ValueError(f"Error getting number: {response}")

    def set_status(self, activation_id: str, status: int) -> str:
        """Set activation status."""
        params = {"id": activation_id, "status": status}
        return self._request("setStatus", params=params)

    def active_status(self, activation_id: str) -> str:
        """Shortcut to set status to 1 (ready)."""
        return self.set_status(activation_id, 1)

    def reactivation_number(self, activation_id: str) -> NumberActivation:
        """
        Request reactivation of a previously used number.
        Action: getExtraActivation
        """
        params = {"activationId": activation_id}
        response = self._request("getExtraActivation", params=params)
        
        # Expected: ACCESS_NUMBER:ID:NUMBER
        if response.startswith("ACCESS_NUMBER"):
            parts = response.split(":")
            new_id = parts[1]
            new_number = parts[2]
            
            # Notify readiness (status 1) as in the original snippet
            self.active_status(new_id)
            
            return NumberActivation(
                activation_id=new_id,
                phone_number=new_number,
                service="reactivation"
            )
        raise ValueError(f"Error reactivating number: {response}")

    def get_status(self, activation_id: str) -> ActivationStatus:
        """Get activation status and SMS code."""
        params = {"id": activation_id}
        response = self._request("getStatus", params=params)
        
        # Expected: STATUS_WAIT_CODE, STATUS_OK:CODE, STATUS_CANCEL, etc.
        if ":" in response:
            status, code = response.split(":", 1)
            return ActivationStatus(status=status, code=code)
        
        return ActivationStatus(status=response)

    def get_sms(self, activation_id: str) -> Optional[str]:
        """
        Polls for SMS code until it arrives or timeout is reached.
        
        Args:
            activation_id: ID of the activation
            timeout: Maximum wait time in seconds
            interval: Time between polls in seconds
        """
        status = self.get_status(activation_id)
        if status.status == "STATUS_OK":
            return status.code
        
        # If status indicates it's finished or cancelled, stop polling
        if status.status in ["STATUS_CANCEL", "NO_ACTIVATION", "ACCESS_CANCEL"]:
            return None
            

    def get_new_sms(self, activation_id: str, timeout: int = 60, interval: int = 5) -> Optional[str]:
        """
        Requests a new SMS for the same number (resend) and waits for it.
        Useful when you need a second code from the same number.
        """
        # Status 3 = Request resending of SMS
        self.set_status(activation_id, 3)
        return self.get_sms(activation_id, timeout=timeout, interval=interval)

    def get_prices(
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
            
        # getPrices usually returns JSON even in the standard API
        response = self._request("getPrices", params=params)
        try:
            import json
            data = json.loads(response)

            print(data)
            
            result = []
            
            # Standardization: some APIs return a list with one dictionary
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
                            
                        # srv_data is usually {"cost": 0.5, "count": 10} or with freePriceMap
                        base_cost = float(srv_data.get("cost", 0) or srv_data.get("price", 0))
                        cost: Union[float, List[float]] = base_cost
                        min_p = base_cost
                        max_p = base_cost
                        
                        # Support for multiple prices if freePriceMap is present
                        free_price_map = srv_data.get("freePriceMap")
                        if isinstance(free_price_map, dict) and free_price_map:
                            prices = sorted([float(p) for p in free_price_map.keys()])
                            if prices:
                                cost = prices
                                min_p = prices[0]
                                max_p = prices[-1]

                        service_map[srv_code] = ServicePrice(
                            service=srv_code,
                            cost=cost,
                            min_price=min_p,
                            max_price=max_p,
                            count=int(srv_data.get("count", 0) or 0)
                        )
                    
                    if service_map:
                        result.append(CountryPrices(country_id=int(country_id), services=service_map))
            return result
        except Exception:
            # If not JSON, we might need a different parser or it's an error
            raise ValueError(f"Error parsing prices or received error: {response}")

    def get_top_countries_by_service(self, service: Optional[str] = None, free_price: Optional[bool] = False) -> List[CountryPrices]:
        """
        Get top countries for a service or all services.
        Action: getTopCountriesByService
        """
        params = {}
        if service:
            params["service"] = service

        if free_price:
            params["freePrice"] = True
            
        response = self._request("getTopCountriesByService", params=params)
        try:
            import json
            data = json.loads(response)
            
            # Pivot data to List[CountryPrices]
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
                
                # Support for multiple prices if freePriceMap is present
                free_price_map = entry.get("freePriceMap")
                if isinstance(free_price_map, dict) and free_price_map:
                    prices = sorted([float(p) for p in free_price_map.keys()])
                    if prices:
                        cost = prices
                        min_p = prices[0]
                        max_p = prices[-1]

                country_map[c_id][srv_code] = ServicePrice(
                    service=srv_code,
                    cost=cost,
                    min_price=min_p,
                    max_price=max_p,
                    count=int(entry.get("count", 0) or 0)
                )

            if service:
                # Can be a List[dict] or a Dict[str, dict] (indexed by "0", "1", ...)
                entries = data
                if isinstance(data, dict):
                    # Handle if the API returns {"service_code": {...}} even when service is requested
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
                # Can be List[Dict[srv, List[dict]]] or Dict[srv, Dict[idx, dict]]
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
