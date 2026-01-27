from typing import Optional
from pyhub.sdk.base.client import ClientBase


class SMS24HClient(ClientBase):
    """
    Client for SMS24HClient API.
    """

    def __init__(
        self,
        api_key: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        base_url: str = "https://api.sms24h.org/stubs/handler_api"
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout
        )
