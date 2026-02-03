from typing import Optional, List
from pyhub.sdk.base.client import ClientBase
from pyhub.sdk.base.schemas import CountryPrices


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
        

    def get_prices(self, service: Optional[str] = None, country: Optional[int] = None,free_price: Optional[bool] = True) -> List[CountryPrices]:
        """
        Overrides get_prices to use getTopCountriesByService for HeroSMS,
        as it provides more detailed data including country mapping.
        """

        # if not country:
        results = self.get_top_countries_by_service(service=service,free_price=free_price)
    
        if country is not None:
            return [r for r in results if r.country_id == country]
            
        return results


        # results = super().get_prices(service=service,country=country,free_price=free_price)

        # return results